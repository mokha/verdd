from rest_framework import serializers

from manageXML.constants import DESC_TRANSLATION, TRANSLATION
from manageXML.models import (
    Example,
    Language,
    Lexeme,
    Relation,
    RelationExample,
    RelationExampleRelation,
)


class ChangedByMixin:
    """Stamp changed_by with the API user and un-approve rows whose content changes."""

    reset_checked_fields = ()

    def create(self, validated_data):
        validated_data["changed_by"] = self.context["request"].user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data["changed_by"] = self.context["request"].user
        if (
            self.reset_checked_fields
            and instance.checked
            and any(
                field in validated_data
                and validated_data[field] != getattr(instance, field)
                for field in self.reset_checked_fields
            )
        ):
            validated_data["checked"] = False
        return super().update(instance, validated_data)


class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = ("id", "name")


class LexemeSerializer(ChangedByMixin, serializers.ModelSerializer):
    language = serializers.PrimaryKeyRelatedField(queryset=Language.objects.all())
    homoId = serializers.IntegerField(min_value=0, required=False)
    web_url = serializers.SerializerMethodField()

    reset_checked_fields = (
        "lexeme",
        "homoId",
        "language",
        "pos",
        "contlex",
        "type",
        "specification",
        "notes",
    )

    class Meta:
        model = Lexeme
        fields = (
            "id",
            "lexeme",
            "homoId",
            "language",
            "pos",
            "contlex",
            "type",
            "specification",
            "notes",
            "checked",
            "added_date",
            "web_url",
        )
        read_only_fields = ("checked", "added_date")

    def get_web_url(self, obj):
        return obj.get_absolute_url()


class RelationExampleSerializer(ChangedByMixin, serializers.ModelSerializer):
    language = serializers.PrimaryKeyRelatedField(queryset=Language.objects.all())
    linked_to = serializers.SerializerMethodField()

    class Meta:
        model = RelationExample
        fields = ("id", "relation", "language", "text", "source", "notes", "linked_to")

    def get_linked_to(self, obj):
        ids = {link.example_to_id for link in obj.example_from_relationexample_set.all()}
        ids |= {link.example_from_id for link in obj.example_to_relationexample_set.all()}
        return sorted(ids)

    def validate(self, attrs):
        if self.instance is not None:
            if "relation" in attrs and attrs["relation"] != self.instance.relation:
                raise serializers.ValidationError(
                    {"relation": "An example cannot be moved to another relation."}
                )
            relation = self.instance.relation
            language = attrs.get("language", self.instance.language)
        else:
            relation = attrs["relation"]
            language = attrs["language"]

        allowed = {relation.lexeme_from.language_id}
        if relation.lexeme_to_id:
            allowed.add(relation.lexeme_to.language_id)
        if language.id not in allowed:
            raise serializers.ValidationError(
                {
                    "language": "Must be one of the relation's languages: %s."
                    % ", ".join(sorted(allowed))
                }
            )
        return attrs


class RelationSerializer(ChangedByMixin, serializers.ModelSerializer):
    lexeme_from = serializers.PrimaryKeyRelatedField(queryset=Lexeme.objects.all())
    lexeme_to = serializers.PrimaryKeyRelatedField(queryset=Lexeme.objects.all())
    examples = RelationExampleSerializer(
        source="relationexample_set", many=True, read_only=True
    )

    reset_checked_fields = ("lexeme_from", "lexeme_to", "type", "notes")

    class Meta:
        model = Relation
        fields = (
            "id",
            "lexeme_from",
            "lexeme_to",
            "type",
            "notes",
            "checked",
            "added_date",
            "examples",
        )
        read_only_fields = ("checked", "added_date")

    def validate(self, attrs):
        lexeme_from = attrs.get("lexeme_from", getattr(self.instance, "lexeme_from", None))
        lexeme_to = attrs.get("lexeme_to", getattr(self.instance, "lexeme_to", None))
        if lexeme_from is not None and lexeme_from == lexeme_to:
            raise serializers.ValidationError(
                "lexeme_from and lexeme_to must be different lexemes."
            )
        return attrs


class ExampleSerializer(ChangedByMixin, serializers.ModelSerializer):
    class Meta:
        model = Example
        fields = ("id", "lexeme", "text", "source", "notes")


class RelationExampleLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = RelationExampleRelation
        fields = ("id", "example_from", "example_to", "notes")

    def validate(self, attrs):
        example_from, example_to = attrs["example_from"], attrs["example_to"]
        if example_from.pk == example_to.pk:
            raise serializers.ValidationError("An example cannot link to itself.")
        if example_from.relation_id != example_to.relation_id:
            raise serializers.ValidationError(
                "Linked examples must belong to the same relation."
            )
        return attrs

    def create(self, validated_data):
        # The model has no changed_by column; history picks the attribute up.
        instance = RelationExampleRelation(**validated_data)
        instance.changed_by = self.context["request"].user
        instance.save()
        return instance


class PairSourceSerializer(serializers.Serializer):
    lexeme = serializers.CharField(max_length=250)
    language = serializers.PrimaryKeyRelatedField(queryset=Language.objects.all())
    pos = serializers.CharField(max_length=25)
    homoId = serializers.IntegerField(min_value=0, required=False)


class PairTargetSerializer(PairSourceSerializer):
    pos = serializers.CharField(max_length=25, required=False)


class PairExampleSerializer(serializers.Serializer):
    source_text = serializers.CharField(max_length=250)
    target_text = serializers.CharField(
        max_length=250, required=False, allow_blank=True
    )
    source = serializers.CharField(max_length=250, required=False, allow_blank=True)
    notes = serializers.CharField(max_length=250, required=False, allow_blank=True)


class PairSerializer(serializers.Serializer):
    source = PairSourceSerializer()
    target = PairTargetSerializer()
    type = serializers.ChoiceField(
        choices=[(TRANSLATION, "Translation"), (DESC_TRANSLATION, "Description translation")],
        default=TRANSLATION,
    )
    notes = serializers.CharField(max_length=250, required=False, allow_blank=True)
    examples = PairExampleSerializer(many=True, required=False, max_length=50)

    def validate(self, attrs):
        if attrs["source"]["language"] == attrs["target"]["language"]:
            raise serializers.ValidationError(
                "source and target must be in different languages."
            )
        return attrs

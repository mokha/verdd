import django_filters

from manageXML.models import Lexeme, Relation


class LexemeFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(field_name="lexeme", lookup_expr="icontains")

    class Meta:
        model = Lexeme
        fields = ["lexeme", "language", "pos", "homoId", "checked"]


class RelationFilter(django_filters.FilterSet):
    lexeme_from = django_filters.NumberFilter()
    lexeme_to = django_filters.NumberFilter()
    from_language = django_filters.CharFilter(field_name="lexeme_from__language")
    to_language = django_filters.CharFilter(field_name="lexeme_to__language")

    class Meta:
        model = Relation
        fields = ["type", "checked"]

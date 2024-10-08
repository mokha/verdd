import string

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Q
from django.urls import reverse
from django.utils.text import slugify
from simple_history.models import HistoricalRecords
from django.core.validators import slug_re
from django.utils import timezone
from .storage import TemporaryFileStorage
from wiki.semantic_api import SemanticAPI
from .common import Rhyme
from .constants import *
from .fields import *
from .managers import *


class Language(models.Model):
    id = models.CharField(
        max_length=3, unique=True, primary_key=True, db_index=True
    )  # ISO 639-3
    name = models.CharField(max_length=250)

    class Meta:
        indexes = [
            models.Index(fields=["id"], name="id_idx"),
        ]

    def __str__(self):
        return self.id

    def __repr__(self):
        return self.id


class DataFile(models.Model):
    lang_source = models.ForeignKey(
        Language, null=True, on_delete=models.SET_NULL, related_name="datafile_source"
    )
    lang_target = models.ForeignKey(
        Language, null=True, on_delete=models.SET_NULL, related_name="datafile_target"
    )
    name = models.CharField(max_length=250)
    added_date = models.DateTimeField("date published", auto_now_add=True)

    def __str__(self):
        return "%s (%d)" % (self.name, self.id)


class Symbol(models.Model):
    name = BinaryCharField(max_length=250, unique=True)
    comment = models.CharField(max_length=250, blank=True)

    @staticmethod
    def all_dict():
        return dict(Symbol.objects.values_list("name", "comment").all())


class Lexeme(models.Model):
    class Meta:
        unique_together = (
            "lexeme",
            "pos",
            "homoId",
            "language",
        )

        indexes = [
            models.Index(
                fields=["lexeme", "pos", "language"], name="lexeme_pos_language_idx"
            ),
            models.Index(fields=["lexeme"], name="lexeme_idx"),
            models.Index(fields=["pos"], name="pos_idx"),
            models.Index(fields=["language"], name="language_idx"),
            models.Index(fields=["lexeme_lang"], name="lexeme_lang_idx"),
            models.Index(fields=["consonance"], name="consonance_idx"),
            models.Index(fields=["consonance_rev"], name="consonance_rev_idx"),
            models.Index(fields=["assonance"], name="assonance_idx"),
            models.Index(fields=["assonance_rev"], name="assonance_rev_idx"),
        ]

    lexeme = BinaryCharField(max_length=250)
    homoId = models.IntegerField(default=0)
    assonance = models.CharField(max_length=250, blank=True)
    assonance_rev = models.CharField(max_length=250, blank=True)
    consonance = models.CharField(max_length=250, blank=True)
    consonance_rev = models.CharField(max_length=250, blank=True)
    lexeme_lang = BinaryCharField(max_length=250, blank=True)
    language = models.ForeignKey(
        Language, null=True, on_delete=models.SET_NULL, related_name="lexemes"
    )
    pos = models.CharField(max_length=25)
    imported_from = models.ForeignKey(
        DataFile, null=True, blank=True, on_delete=models.CASCADE
    )
    notes = models.CharField(max_length=250, blank=True)
    added_date = models.DateTimeField("date published", auto_now_add=True)
    contlex = models.CharField(max_length=250, blank=True)
    type = models.CharField(max_length=25, blank=True)
    lemmaId = models.CharField(max_length=250, blank=True, default="")
    inflexId = models.CharField(max_length=25, blank=True)
    inflexType = models.IntegerField(
        choices=INFLEX_TYPE_OPTIONS, blank=True, null=True, default=None
    )
    checked = models.BooleanField(default=False)
    specification = models.CharField(max_length=250, blank=True)

    deleted = models.BooleanField(default=False)
    changed_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="lexemes"
    )
    history = HistoricalRecords()

    def __str__(self):
        return self.lexeme

    def full_str(self):
        return "{} ({})".format(self.lexeme, self.pos)

    def slug(self):
        _ls = self.lexeme.strip()
        slug = slugify(_ls)
        if slug_re.match(slug):
            return slug
        return "NA"

    def get_absolute_url(self):
        return reverse("lexeme-detail", kwargs={"pk": self.pk})

    def get_assonance(self):
        return Rhyme.assonance(self.lexeme)

    def get_assonance_rev(self):
        return Rhyme.assonance_rev(self.lexeme)

    def get_consonance(self):
        return Rhyme.consonance(self.lexeme)

    def get_consonance_rev(self):
        return Rhyme.consonance_rev(self.lexeme)

    def get_relations(self):
        return Relation.objects.filter(Q(lexeme_from=self) | Q(lexeme_to=self))

    def get_translations(self):
        return Relation.objects.filter(lexeme_from=self, type=TRANSLATION)

    def inflexType_str(self):
        return (
            INFLEX_TYPE_OPTIONS_DICT[self.inflexType]
            if self.inflexType in INFLEX_TYPE_OPTIONS_DICT
            else ""
        )

    @property
    def homonyms_count(self):
        """
        Returns the count of homonyms for this lexeme (lexeme with the same lexeme, pos, and language).
        If the count has been pre-calculated (e.g., annotated in a queryset), use the cached value.
        """
        if hasattr(self, "_homonyms_count"):
            return self._homonyms_count
        return Lexeme.objects.filter(
            lexeme=self.lexeme, pos=self.pos, language=self.language
        ).count()

    def get_lexeme_lang(self):
        main_str = " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~¨ÂÄÅÕÖáâäåõöČčĐđŊŋśŠšŽžƷǤǥǦǧǨǩǮǯʒʹʼˈАаẸẹ’₋"
        _sms_str = " !\"#$%&'()*+,-./0123456789:;<=>?@AАÂBCČƷǮDĐEẸFGǦǤHIJKǨLMNŊOÕPQRSŠTUVWXYZŽÅÄÖ[\\]^_`аaâbcčʒǯdđeẹfgǧǥhijkǩlmnŋoõpqrsštuvwxyzžåäöáś¨{|}ʹʼˈ~₋’"
        _fin_str = " !\"#$%&'()*+,-./0123456789:;<=>?@AАBCDEFGHIJKLMNOPQRSŠTUVWXYZÅÄÖ[\\]^_₋`аabcdefghijklmnopqrsštuvwxyzåäö¨{|}ʹʼ’ˈÂČƷǮĐẸǦǤǨŊÕŽâáčʒǯđẹǧǥǩŋõśž~"

        IGNORE_CHARACTERS = " -ʹʼˈ" + string.punctuation
        LANGUAGE_SORT = {
            "sms": dict([(x, main_str[_sms_str.index(x)]) for x in _sms_str]),
            "fin": dict([(x, main_str[_fin_str.index(x)]) for x in _fin_str]),
        }
        if self.language in LANGUAGE_SORT:
            sort_dict = LANGUAGE_SORT[self.language]
            # return ''.join([sort_dict[c] if c in sort_dict else c for c in self.lexeme.upper()])
            return "".join(
                [
                    sort_dict[c]
                    for c in self.lexeme.upper()
                    if c in sort_dict and c not in IGNORE_CHARACTERS
                ]
            )
        return self.lexeme

    def find_akusanat_affiliation(self):
        semAPI = SemanticAPI()
        r1 = semAPI.ask(
            query=(
                "[[%s:%s]]" % (self.language.id.capitalize(), self.lexeme),
                "?Category",
                "?POS",
                "?Lang",
                "?Contlex",
            )
        )

        if "query" in r1 and "results" in r1["query"] and r1["query"]["results"]:
            title, info = r1["query"]["results"].popitem()
            return title
        return None

    def save(self, *args, **kwargs):
        # store rhyming features
        self.assonance = self.get_assonance()
        self.assonance_rev = self.get_assonance_rev()
        self.consonance = self.get_consonance()
        self.consonance_rev = self.get_consonance_rev()
        self.lexeme_lang = self.get_lexeme_lang()

        # automatically get the inflexType
        if (not self.inflexType or self.inflexType == 0) and self.contlex:
            for inflexType, inflexType_list in INFLEX_TYPE_MAPPINGS.items():
                if self.contlex in inflexType_list:
                    self.inflexType = inflexType
                    break
            else:
                self.inflexType = INFLEX_TYPE_X

        return super(Lexeme, self).save(*args, **kwargs)

    @property
    def _history_user(self):
        return self.changed_by

    @_history_user.setter
    def _history_user(self, value):
        self.changed_by = value

    def metadata_str(self, sep="__"):
        _metadata = self.lexememetadata_set.order_by("text").values_list(
            "text", flat=True
        )
        return sep.join(_metadata) if _metadata else ""

    def symbols(self):
        from apertium.constants import POS_tags_rev

        _metadata = list(
            self.lexememetadata_set.filter(type=GENERIC_METADATA).values_list(
                "text", flat=True
            )
        )
        pos_c = self.pos.upper()
        if pos_c in POS_tags_rev:
            pos = POS_tags_rev[pos_c]
            if (
                pos == "n"
                and self.lexememetadata_set.filter(
                    type=LEXEME_TYPE, text__iexact="Prop"
                ).all()
            ):
                _metadata += [
                    "np",
                ]
            else:
                _metadata += [
                    pos,
                ]
        return _metadata


class Relation(models.Model):
    class Meta:
        unique_together = ("lexeme_from", "lexeme_to", "type")

        indexes = [
            models.Index(
                fields=["lexeme_from"], name="lexeme_from_idx"
            ),  # For faster joins and lookups
            models.Index(
                fields=["lexeme_to"], name="lexeme_to_idx"
            ),  # For faster joins and lookups
            models.Index(fields=["type"], name="type_idx"),  # For filtering by type
            models.Index(
                fields=["checked"], name="checked_idx"
            ),  # For filtering by checked status
        ]

    lexeme_from = models.ForeignKey(
        Lexeme, related_name="lexeme_from_lexeme_set", on_delete=models.CASCADE
    )
    lexeme_to = models.ForeignKey(
        Lexeme,
        null=True,
        blank=True,
        related_name="lexeme_to_lexeme_set",
        on_delete=models.CASCADE,
    )
    type = models.IntegerField(choices=RELATION_TYPE_OPTIONS, default=0)
    notes = models.CharField(max_length=250, blank=True)

    checked = models.BooleanField(default=False)
    added_date = models.DateTimeField("date published", auto_now_add=True)
    deleted = models.BooleanField(default=False)
    changed_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="relations"
    )
    history = HistoricalRecords()

    def __str__(self):
        return "%s - %s" % (
            self.lexeme_from.lexeme,
            self.lexeme_to.lexeme if self.lexeme_to else "",
        )

    def full_str(self):
        return "{}  - {}".format(self.lexeme_from.full_str(), self.lexeme_to.full_str())

    def type_str(self):
        return (
            RELATION_TYPE_OPTIONS_DICT[self.type]
            if self.type in RELATION_TYPE_OPTIONS_DICT
            else ""
        )

    def get_absolute_url(self):
        return reverse("relation-detail", kwargs={"pk": self.pk})

    @property
    def _history_user(self):
        return self.changed_by

    @_history_user.setter
    def _history_user(self, value):
        self.changed_by = value

    def save(self, *args, **kwargs):
        super(Relation, self).save(*args, **kwargs)

        if self.type in REVERSE_RELATION_MAPPING:
            reverse_relation, created = Relation.objects.get_or_create(
                lexeme_from=self.lexeme_to,
                lexeme_to=self.lexeme_from,
                type=REVERSE_RELATION_MAPPING[self.type],
                defaults={"notes": self.notes, "checked": self.checked},
            )


class Source(models.Model):
    class Meta:
        unique_together = ("relation", "name")

    relation = models.ForeignKey(Relation, on_delete=models.CASCADE)
    name = models.CharField(max_length=250)
    page = models.CharField(max_length=25, blank=True)
    type = models.CharField(max_length=25)
    notes = models.CharField(max_length=250, blank=True)
    added_date = models.DateTimeField("date published", auto_now_add=True)
    changed_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="sources"
    )
    history = HistoricalRecords()

    def __str__(self):
        return "(%s) %s" % (self.type, self.name)

    def get_absolute_url(self):
        return reverse("relation-detail", kwargs={"pk": self.relation.pk})

    @property
    def _history_user(self):
        return self.changed_by

    @_history_user.setter
    def _history_user(self, value):
        self.changed_by = value


class MiniParadigm(models.Model):
    lexeme = models.ForeignKey(Lexeme, on_delete=models.CASCADE)
    msd = models.CharField(max_length=25)
    wordform = models.CharField(max_length=250)
    changed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="miniparadigms",
    )
    history = HistoricalRecords()

    def __str__(self):
        return "%s: %s" % (self.msd, self.wordform)

    def full_str(self):
        return "%s - %s: %s" % (self.lexeme.full_str(), self.msd, self.wordform)

    def get_absolute_url(self):
        return reverse("lexeme-detail", kwargs={"pk": self.lexeme.pk})

    @property
    def _history_user(self):
        return self.changed_by

    @_history_user.setter
    def _history_user(self, value):
        self.changed_by = value


class Affiliation(models.Model):
    class Meta:
        unique_together = ("lexeme", "title", "link", "type")

    lexeme = models.ForeignKey(Lexeme, on_delete=models.CASCADE)
    title = models.CharField(max_length=250)
    link = models.URLField(null=True, default=None)
    type = models.IntegerField(
        choices=AFFILIATION_TYPES, blank=True, null=True, default=None
    )
    checked = models.BooleanField(default=False)
    notes = models.CharField(max_length=250, blank=True)
    changed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="affiliations",
    )
    history = HistoricalRecords()

    def get_absolute_url(self):
        return reverse("lexeme-detail", kwargs={"pk": self.lexeme.pk})

    @property
    def _history_user(self):
        return self.changed_by

    @_history_user.setter
    def _history_user(self, value):
        self.changed_by = value


class Example(models.Model):
    class Meta:
        unique_together = ("lexeme", "text")

    lexeme = models.ForeignKey(Lexeme, on_delete=models.CASCADE)
    text = models.CharField(max_length=250)
    source = models.CharField(max_length=250, blank=True)
    notes = models.CharField(max_length=250, blank=True)
    changed_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="examples"
    )
    history = HistoricalRecords()

    def __str__(self):
        return self.text

    def get_absolute_url(self):
        return reverse("lexeme-detail", kwargs={"pk": self.lexeme.pk})

    @property
    def _history_user(self):
        return self.changed_by

    @_history_user.setter
    def _history_user(self, value):
        self.changed_by = value


class RelationMetadata(models.Model):
    class Meta:
        unique_together = ("relation", "language", "type", "text")

    relation = models.ForeignKey(Relation, on_delete=models.CASCADE)
    text = models.CharField(max_length=250)
    language = models.ForeignKey(
        Language, null=True, on_delete=models.SET_NULL, related_name="relation_metadata"
    )
    type = models.IntegerField(
        choices=RELATION_METADATA_TYPES, blank=True, null=True, default=None
    )
    changed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="relation_metadata",
    )
    history = HistoricalRecords()

    def __str__(self):
        return "({}) {}".format(self.language, self.text)

    def get_absolute_url(self):
        return reverse("relation-detail", kwargs={"pk": self.relation.pk})

    @property
    def _history_user(self):
        return self.changed_by

    @_history_user.setter
    def _history_user(self, value):
        self.changed_by = value


class RelationExample(models.Model):
    class Meta:
        unique_together = ("relation", "language", "text")

    relation = models.ForeignKey(Relation, on_delete=models.CASCADE)
    text = models.CharField(max_length=250)
    language = models.ForeignKey(
        Language, null=True, on_delete=models.SET_NULL, related_name="relation_examples"
    )
    source = models.CharField(max_length=250, blank=True)
    notes = models.CharField(max_length=250, blank=True)
    changed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="relation_examples",
    )
    history = HistoricalRecords()

    def __str__(self):
        return "({}-{}) {}".format(self.id, self.language, self.text)

    def get_absolute_url(self):
        return reverse("relation-detail", kwargs={"pk": self.relation.pk})

    @property
    def _history_user(self):
        return self.changed_by

    @_history_user.setter
    def _history_user(self, value):
        self.changed_by = value

    def linked_examples(self):
        return self.example_from_relationexample_set.all()


class RelationExampleRelation(models.Model):
    class Meta:
        unique_together = ("example_from", "example_to")

    example_from = models.ForeignKey(
        RelationExample,
        related_name="example_from_relationexample_set",
        on_delete=models.CASCADE,
    )
    example_to = models.ForeignKey(
        RelationExample,
        related_name="example_to_relationexample_set",
        on_delete=models.CASCADE,
    )
    notes = models.CharField(max_length=250, blank=True)
    history = HistoricalRecords()

    def __str__(self):
        return "{} {}".format(self.example_from, self.example_to)

    def get_absolute_url(self):
        return reverse("relation-detail", kwargs={"pk": self.example_from.relation.pk})

    @property
    def _history_user(self):
        return self.changed_by

    @_history_user.setter
    def _history_user(self, value):
        self.changed_by = value


class LexemeMetadata(models.Model):
    class Meta:
        unique_together = (
            "lexeme",
            "type",
            "text",
        )

    lexeme = models.ForeignKey(Lexeme, on_delete=models.CASCADE)
    type = models.IntegerField(
        choices=LEXEME_METADATA_TYPES, blank=True, null=True, default=None
    )
    text = models.CharField(max_length=250)
    changed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lexeme_metadata",
    )
    history = HistoricalRecords()

    def __str__(self):
        return "{}".format(self.text)

    def get_absolute_url(self):
        return reverse("lexeme-detail", kwargs={"pk": self.lexeme.pk})

    @property
    def _history_user(self):
        return self.changed_by

    @_history_user.setter
    def _history_user(self, value):
        self.changed_by = value


class Stem(models.Model):
    class Meta:
        unique_together = ("lexeme", "text", "contlex")

    lexeme = models.ForeignKey(Lexeme, on_delete=models.CASCADE)
    text = BinaryCharField(max_length=250)
    homoId = models.IntegerField(default=0)
    contlex = models.CharField(max_length=250, blank=True)
    notes = models.CharField(max_length=250, blank=True)
    order = models.IntegerField(default=0)
    status = models.CharField(max_length=250, blank=True)

    checked = models.BooleanField(default=False)
    added_date = models.DateTimeField("date published", auto_now_add=True)
    changed_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="stems"
    )
    history = HistoricalRecords()

    def get_absolute_url(self):
        return reverse("stem-detail", kwargs={"pk": self.pk})

    @property
    def _history_user(self):
        return self.changed_by

    @_history_user.setter
    def _history_user(self, value):
        self.changed_by = value


class StemMetadata(models.Model):
    class Meta:
        unique_together = (
            "stem",
            "type",
            "text",
        )

    stem = models.ForeignKey(Stem, on_delete=models.CASCADE)
    type = models.IntegerField(
        choices=STEM_METADATA_TYPES, blank=True, null=True, default=None
    )
    text = models.CharField(max_length=250)
    changed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stem_metadata",
    )
    history = HistoricalRecords()

    def __str__(self):
        return "{}".format(self.text)

    def get_absolute_url(self):
        return reverse("stem-detail", kwargs={"pk": self.stem.pk})

    @property
    def _history_user(self):
        return self.changed_by

    @_history_user.setter
    def _history_user(self, value):
        self.changed_by = value


class LanguageParadigm(models.Model):
    class Meta:
        unique_together = (
            "language",
            "pos",
            "form",
        )

    language = models.ForeignKey(
        Language, null=True, on_delete=models.SET_NULL, related_name="paradigms"
    )
    pos = models.CharField(max_length=25)
    form = models.CharField(max_length=250, blank=True)
    mini = models.BooleanField(default=False)
    changed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="language_paradigms",
    )
    history = HistoricalRecords()

    def __str__(self):
        return "{}".format(self.form)

    @property
    def _history_user(self):
        return self.changed_by

    @_history_user.setter
    def _history_user(self, value):
        self.changed_by = value

    def save(self, *args, **kwargs):
        super(LanguageParadigm, self).save(*args, **kwargs)
        cache.delete(f"language_paradigms_{self.language.id}")

    def delete(self, *args, **kwargs):
        cache.delete(f"language_paradigms_{self.language.id}")
        super(LanguageParadigm, self).delete(*args, **kwargs)


class FileRequest(models.Model):

    type = models.IntegerField(
        choices=DOWNLOAD_TYPES, blank=True, null=True, default=None
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="file_requests",
    )
    status = models.CharField(
        max_length=10, choices=DOWNLOAD_STATUS_CHOICES, default=DOWNLOAD_STATUS_PENDING
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    options = models.TextField(blank=True, null=True)
    lang_source = models.ForeignKey(
        Language,
        null=True,
        on_delete=models.SET_NULL,
        related_name="file_requests_lang_source",
    )
    lang_target = models.ForeignKey(
        Language,
        null=True,
        on_delete=models.SET_NULL,
        related_name="file_requests_lang_target",
    )

    file = models.FileField(
        upload_to="files/", blank=True, null=True, storage=TemporaryFileStorage
    )
    output = models.TextField(blank=True, null=True)

    deleted = models.BooleanField(default=False)

    processed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Request {self.id} by {self.user.username}"

    def is_completed(self):
        return self.status == DOWNLOAD_STATUS_COMPLETED

    def is_failed(self):
        return self.status == DOWNLOAD_STATUS_FAILED

    def is_processing(self):
        return self.status == DOWNLOAD_STATUS_PROCESSING

    def is_pending(self):
        return self.status == DOWNLOAD_STATUS_PENDING

    def time_taken(self):
        if self.processed_at:
            delta = self.processed_at - self.created_at
            minutes = delta.total_seconds() / 60
            return round(minutes, 2)
        return None

    def get_absolute_url(self):
        return reverse("file-download", kwargs={"pk": self.pk})

    def mark_processing(self):
        self.status = DOWNLOAD_STATUS_PROCESSING
        self.save()

    def mark_completed(self, file_path, output=None):
        self.status = DOWNLOAD_STATUS_COMPLETED
        self.file.name = file_path
        self.output = output
        self.processed_at = timezone.now()
        self.save()

    def mark_failed(self, error_message):
        self.status = DOWNLOAD_STATUS_FAILED
        self.output = error_message
        self.processed_at = timezone.now()
        self.save()

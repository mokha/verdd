from django.db import models
from simple_history.models import HistoricalRecords
from django.db.models import Q
from django.utils.text import slugify
from django.urls import reverse
from .common import Rhyme
from .constants import *


class DataFile(models.Model):
    lang_source = models.CharField(max_length=3)
    lang_target = models.CharField(max_length=3)
    name = models.CharField(max_length=250)
    added_date = models.DateTimeField('date published', auto_now_add=True)

    def __str__(self):
        return "%s (%d)" % (self.name, self.id)


class Lexeme(models.Model):
    class Meta:
        unique_together = ('lexeme', 'pos', 'homoId', 'language',)

    lexeme = models.CharField(max_length=250)
    homoId = models.IntegerField(default=0)
    assonance = models.CharField(max_length=250, blank=True)
    assonance_rev = models.CharField(max_length=250, blank=True)
    consonance = models.CharField(max_length=250, blank=True)
    consonance_rev = models.CharField(max_length=250, blank=True)
    language = models.CharField(max_length=3)
    pos = models.CharField(max_length=25)
    imported_from = models.ForeignKey(DataFile, null=True, blank=True, on_delete=models.CASCADE)
    notes = models.CharField(max_length=250, blank=True)
    added_date = models.DateTimeField('date published', auto_now_add=True)
    contlex = models.CharField(max_length=250, blank=True)
    type = models.CharField(max_length=25, blank=True)
    lemmaId = models.CharField(max_length=250, blank=True, default='')
    inflexId = models.CharField(max_length=25, blank=True)
    inflexType = models.IntegerField(choices=INFLEX_TYPE_OPTIONS,
                                     blank=True, null=True, default=None)
    deleted = models.BooleanField(default=False)
    history = HistoricalRecords()

    def __str__(self):
        return self.lexeme

    def slug(self):
        return slugify(self.lexeme) if self.lexeme else 'NA'

    def get_absolute_url(self):
        return reverse('lexeme-detail', kwargs={'pk': self.pk})

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

    def inflexType_str(self):
        return INFLEX_TYPE_OPTIONS_DICT[self.inflexType] if self.inflexType in INFLEX_TYPE_OPTIONS_DICT else ''

    def save(self, *args, **kwargs):
        # store rhyming features
        self.assonance = self.get_assonance()
        self.assonance_rev = self.get_assonance_rev()
        self.consonance = self.get_consonance()
        self.consonance_rev = self.get_consonance_rev()

        # automatically get the inflexType
        if (not self.inflexType or self.inflexType == 0) and self.contlex:
            for inflexType, inflexType_list in INFLEX_TYPE_MAPPINGS.items():
                if self.contlex in inflexType_list:
                    self.inflexType = inflexType
                    break
            self.inflexType = INFLEX_TYPE_X

        return super(Lexeme, self).save(*args, **kwargs)


class Relation(models.Model):
    class Meta:
        unique_together = ('lexeme_from', 'lexeme_to', 'type')

    lexeme_from = models.ForeignKey(Lexeme, related_name='lexeme_from_lexeme_set', on_delete=models.CASCADE)
    lexeme_to = models.ForeignKey(Lexeme, related_name='lexeme_to_lexeme_set', on_delete=models.CASCADE)
    type = models.IntegerField(choices=RELATION_TYPE_OPTIONS,
                               default=0)
    notes = models.CharField(max_length=250, blank=True)
    checked = models.BooleanField(default=False)
    added_date = models.DateTimeField('date published', auto_now_add=True)
    deleted = models.BooleanField(default=False)
    history = HistoricalRecords()

    def __str__(self):
        return "%s - %s" % (self.lexeme_from.lexeme, self.lexeme_to.lexeme)

    def type_str(self):
        return RELATION_TYPE_OPTIONS_DICT[self.type] if self.type in RELATION_TYPE_OPTIONS_DICT else ''

    def get_absolute_url(self):
        return reverse('relation-detail',
                       kwargs={'pk': self.pk})


class Source(models.Model):
    class Meta:
        unique_together = ('relation', 'name')

    relation = models.ForeignKey(Relation, on_delete=models.CASCADE)
    name = models.CharField(max_length=250)
    page = models.CharField(max_length=25, blank=True)
    type = models.CharField(max_length=25)
    notes = models.CharField(max_length=250, blank=True)
    added_date = models.DateTimeField('date published', auto_now_add=True)
    history = HistoricalRecords()

    def __str__(self):
        return "(%s) %s" % (self.type, self.name)

    def get_absolute_url(self):
        return reverse('relation-detail',
                       kwargs={'pk': self.relation.pk})


class MiniParadigm(models.Model):
    lexeme = models.ForeignKey(Lexeme, on_delete=models.CASCADE)
    msd = models.CharField(max_length=25)
    wordform = models.CharField(max_length=250)
    history = HistoricalRecords()

    def __str__(self):
        return "%s: %s" % (self.msd, self.wordform)

    def get_absolute_url(self):
        return reverse('lexeme-detail',
                       kwargs={'pk': self.lexeme.pk})


class Affiliation(models.Model):
    class Meta:
        unique_together = ('lexeme', 'title')

    lexeme = models.ForeignKey(Lexeme, on_delete=models.CASCADE)
    title = models.CharField(max_length=250)


class Examples(models.Model):
    class Meta:
        unique_together = ('lexeme', 'text')

    lexeme = models.ForeignKey(Lexeme, on_delete=models.CASCADE)
    text = models.CharField(max_length=250)
    history = HistoricalRecords()

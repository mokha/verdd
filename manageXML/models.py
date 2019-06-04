from django.db import models
from simple_history.models import HistoricalRecords
from django.utils.text import slugify
from django.urls import reverse


class DataFile(models.Model):
    lang_source = models.CharField(max_length=3)
    lang_target = models.CharField(max_length=3)
    name = models.CharField(max_length=250)
    added_date = models.DateTimeField('date published', auto_now_add=True)

    def __str__(self):
        return "%s (%d)" % (self.name, self.id)


class Element(models.Model):
    lexeme = models.CharField(max_length=250)
    language = models.CharField(max_length=3)
    pos = models.CharField(max_length=25)
    imported_from = models.ForeignKey(DataFile, null=True, blank=True, on_delete=models.CASCADE)
    notes = models.CharField(max_length=250)
    added_date = models.DateTimeField('date published', auto_now_add=True)
    checked = models.BooleanField(default=False)
    history = HistoricalRecords()

    def __str__(self):
        return self.lexeme

    def slug(self):
        return slugify(self.lexeme) if self.lexeme else 'NA'

    def get_absolute_url(self):
        return reverse('element-detail', kwargs={'pk': self.pk, 'slug': self.slug})


class Stem(models.Model):
    element = models.ForeignKey(Element, on_delete=models.CASCADE)
    contlex = models.CharField(max_length=250)
    text = models.CharField(max_length=250)
    inflexId = models.CharField(max_length=25, blank=True)
    added_date = models.DateTimeField('date published', auto_now_add=True)

    def __str__(self):
        return self.text


class Etymon(models.Model):
    element = models.ForeignKey(Element, on_delete=models.CASCADE)
    text = models.CharField(max_length=250)
    language = models.CharField(max_length=3)
    added_date = models.DateTimeField('date published', auto_now_add=True)
    history = HistoricalRecords()

    def __str__(self):
        return self.text


class Translation(models.Model):
    element = models.ForeignKey(Element, on_delete=models.CASCADE)
    text = models.CharField(max_length=250)
    language = models.CharField(max_length=3)
    pos = models.CharField(max_length=25)
    contlex = models.CharField(max_length=250)
    type = models.CharField(max_length=25)
    lemmaId = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE)
    inflexId = models.CharField(max_length=25, blank=True)
    notes = models.CharField(max_length=250)
    added_date = models.DateTimeField('date published', auto_now_add=True)
    history = HistoricalRecords()

    def __str__(self):
        return self.text

    def slug(self):
        return slugify(self.element.lexeme + "-" + self.text) if self.text and self.element.lexeme else 'NA'

    def get_absolute_url(self):
        return reverse('translation-detail', kwargs={'pk': self.pk, 'slug': self.slug})


class Source(models.Model):
    translation = models.ForeignKey(Translation, on_delete=models.CASCADE)
    name = models.CharField(max_length=250)
    page = models.CharField(max_length=25, blank=True)
    type = models.CharField(max_length=25)
    notes = models.CharField(max_length=250)
    added_date = models.DateTimeField('date published', auto_now_add=True)
    history = HistoricalRecords()

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('element-detail',
                       kwargs={'pk': self.translation.element.pk, 'slug': self.translation.element.slug()})


class MiniParadigm(models.Model):
    translation = models.ForeignKey(Translation, on_delete=models.CASCADE)
    msd = models.CharField(max_length=25)
    wordform = models.CharField(max_length=250)
    history = HistoricalRecords()

    def __str__(self):
        return "%s: %s" % (self.msd, self.wordform)

    def get_absolute_url(self):
        return reverse('element-detail',
                       kwargs={'pk': self.translation.element.pk, 'slug': self.translation.element.slug()})


class Affiliation(models.Model):
    translation = models.ForeignKey(Translation, on_delete=models.CASCADE)
    title = models.CharField(max_length=250)

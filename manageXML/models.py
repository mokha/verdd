from django.db import models


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
    added_date = models.DateTimeField('date published', auto_now_add=True)

    def __str__(self):
        return self.lexeme


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

    def __str__(self):
        return self.text


class Source(models.Model):
    element = models.ForeignKey(Element, on_delete=models.CASCADE)
    name = models.CharField(max_length=250)
    page = models.CharField(max_length=25, blank=True)
    type = models.CharField(max_length=25)
    added_date = models.DateTimeField('date published', auto_now_add=True)

    def __str__(self):
        return self.name


class Translation(models.Model):
    element = models.ForeignKey(Element, on_delete=models.CASCADE)
    text = models.CharField(max_length=250)
    language = models.CharField(max_length=3)
    pos = models.CharField(max_length=25)
    added_date = models.DateTimeField('date published', auto_now_add=True)

    def __str__(self):
        return self.text

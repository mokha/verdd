# Generated by Django 2.2.1 on 2020-07-01 19:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('manageXML', '0017_historicalrelationexamplerelation_relationexamplerelation'),
    ]

    operations = [
        migrations.AddField(
            model_name='example',
            name='notes',
            field=models.CharField(blank=True, max_length=250),
        ),
        migrations.AddField(
            model_name='historicalexample',
            name='notes',
            field=models.CharField(blank=True, max_length=250),
        ),
        migrations.AddField(
            model_name='historicalrelationexample',
            name='notes',
            field=models.CharField(blank=True, max_length=250),
        ),
        migrations.AddField(
            model_name='historicalrelationexamplerelation',
            name='notes',
            field=models.CharField(blank=True, max_length=250),
        ),
        migrations.AddField(
            model_name='relationexample',
            name='notes',
            field=models.CharField(blank=True, max_length=250),
        ),
        migrations.AddField(
            model_name='relationexamplerelation',
            name='notes',
            field=models.CharField(blank=True, max_length=250),
        ),
    ]
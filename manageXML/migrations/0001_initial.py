# Generated by Django 2.2.1 on 2019-05-22 23:00

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Element',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('lexeme', models.CharField(max_length=250)),
                ('language', models.CharField(max_length=3)),
                ('pos', models.CharField(max_length=25)),
                ('added_date', models.DateTimeField(verbose_name='date published')),
            ],
        ),
        migrations.CreateModel(
            name='Translation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.CharField(max_length=250)),
                ('language', models.CharField(max_length=3)),
                ('pos', models.CharField(max_length=25)),
                ('added_date', models.DateTimeField(verbose_name='date published')),
                ('element', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='manageXML.Element')),
            ],
        ),
        migrations.CreateModel(
            name='Stem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('contlex', models.CharField(max_length=250)),
                ('text', models.CharField(max_length=250)),
                ('inflexId', models.CharField(blank=True, max_length=25)),
                ('added_date', models.DateTimeField(verbose_name='date published')),
                ('element', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='manageXML.Element')),
            ],
        ),
        migrations.CreateModel(
            name='Source',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=250)),
                ('page', models.CharField(blank=True, max_length=25)),
                ('type', models.CharField(max_length=25)),
                ('added_date', models.DateTimeField(verbose_name='date published')),
                ('element', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='manageXML.Element')),
            ],
        ),
        migrations.CreateModel(
            name='Etymon',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.CharField(max_length=250)),
                ('language', models.CharField(max_length=3)),
                ('added_date', models.DateTimeField(verbose_name='date published')),
                ('element', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='manageXML.Element')),
            ],
        ),
    ]
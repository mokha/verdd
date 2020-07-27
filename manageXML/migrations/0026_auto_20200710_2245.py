# Generated by Django 2.2.1 on 2020-07-10 22:45

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('manageXML', '0025_auto_20200710_1323'),
    ]

    operations = [
        migrations.AlterField(
            model_name='datafile',
            name='lang_source',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='datafile_source', to='manageXML.Language'),
        ),
        migrations.AlterField(
            model_name='datafile',
            name='lang_target',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='datafile_target', to='manageXML.Language'),
        ),
    ]
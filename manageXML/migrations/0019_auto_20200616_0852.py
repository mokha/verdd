# Generated by Django 2.2.1 on 2020-06-16 08:52

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("manageXML", "0018_auto_20200616_0844"),
    ]

    operations = [
        migrations.AlterField(
            model_name="relation",
            name="lexeme_to",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="lexeme_to_lexeme_set",
                to="manageXML.Lexeme",
            ),
        ),
    ]

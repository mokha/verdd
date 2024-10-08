# Generated by Django 5.1 on 2024-09-05 15:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("manageXML", "0034_alter_language_id_language_id_idx"),
    ]

    operations = [
        migrations.AlterField(
            model_name="historicalrelation",
            name="type",
            field=models.IntegerField(
                choices=[
                    (0, "Translation"),
                    (1, "Etymology"),
                    (2, "Compound"),
                    (3, "Derivation"),
                    (4, "Variation"),
                    (5, "Phraseology"),
                    (8, "Hyponymy"),
                    (9, "Hyperonymy"),
                    (10, "Holonymy"),
                    (11, "Meronymy"),
                    (12, "Co-hyponym"),
                    (6, "Synonym"),
                    (7, "Antonym"),
                    (13, "Description translation"),
                    (99, "Other"),
                ],
                default=0,
            ),
        ),
        migrations.AlterField(
            model_name="relation",
            name="type",
            field=models.IntegerField(
                choices=[
                    (0, "Translation"),
                    (1, "Etymology"),
                    (2, "Compound"),
                    (3, "Derivation"),
                    (4, "Variation"),
                    (5, "Phraseology"),
                    (8, "Hyponymy"),
                    (9, "Hyperonymy"),
                    (10, "Holonymy"),
                    (11, "Meronymy"),
                    (12, "Co-hyponym"),
                    (6, "Synonym"),
                    (7, "Antonym"),
                    (13, "Description translation"),
                    (99, "Other"),
                ],
                default=0,
            ),
        ),
    ]

# Generated by Django 5.1 on 2024-08-25 18:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("manageXML", "0029_auto_20210810_2054"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="historicalaffiliation",
            options={
                "get_latest_by": ("history_date", "history_id"),
                "ordering": ("-history_date", "-history_id"),
                "verbose_name": "historical affiliation",
                "verbose_name_plural": "historical affiliations",
            },
        ),
        migrations.AlterModelOptions(
            name="historicalexample",
            options={
                "get_latest_by": ("history_date", "history_id"),
                "ordering": ("-history_date", "-history_id"),
                "verbose_name": "historical example",
                "verbose_name_plural": "historical examples",
            },
        ),
        migrations.AlterModelOptions(
            name="historicallexeme",
            options={
                "get_latest_by": ("history_date", "history_id"),
                "ordering": ("-history_date", "-history_id"),
                "verbose_name": "historical lexeme",
                "verbose_name_plural": "historical lexemes",
            },
        ),
        migrations.AlterModelOptions(
            name="historicallexememetadata",
            options={
                "get_latest_by": ("history_date", "history_id"),
                "ordering": ("-history_date", "-history_id"),
                "verbose_name": "historical lexeme metadata",
                "verbose_name_plural": "historical lexeme metadatas",
            },
        ),
        migrations.AlterModelOptions(
            name="historicalminiparadigm",
            options={
                "get_latest_by": ("history_date", "history_id"),
                "ordering": ("-history_date", "-history_id"),
                "verbose_name": "historical mini paradigm",
                "verbose_name_plural": "historical mini paradigms",
            },
        ),
        migrations.AlterModelOptions(
            name="historicalrelation",
            options={
                "get_latest_by": ("history_date", "history_id"),
                "ordering": ("-history_date", "-history_id"),
                "verbose_name": "historical relation",
                "verbose_name_plural": "historical relations",
            },
        ),
        migrations.AlterModelOptions(
            name="historicalrelationexample",
            options={
                "get_latest_by": ("history_date", "history_id"),
                "ordering": ("-history_date", "-history_id"),
                "verbose_name": "historical relation example",
                "verbose_name_plural": "historical relation examples",
            },
        ),
        migrations.AlterModelOptions(
            name="historicalrelationexamplerelation",
            options={
                "get_latest_by": ("history_date", "history_id"),
                "ordering": ("-history_date", "-history_id"),
                "verbose_name": "historical relation example relation",
                "verbose_name_plural": "historical relation example relations",
            },
        ),
        migrations.AlterModelOptions(
            name="historicalrelationmetadata",
            options={
                "get_latest_by": ("history_date", "history_id"),
                "ordering": ("-history_date", "-history_id"),
                "verbose_name": "historical relation metadata",
                "verbose_name_plural": "historical relation metadatas",
            },
        ),
        migrations.AlterModelOptions(
            name="historicalsource",
            options={
                "get_latest_by": ("history_date", "history_id"),
                "ordering": ("-history_date", "-history_id"),
                "verbose_name": "historical source",
                "verbose_name_plural": "historical sources",
            },
        ),
        migrations.AlterModelOptions(
            name="historicalstem",
            options={
                "get_latest_by": ("history_date", "history_id"),
                "ordering": ("-history_date", "-history_id"),
                "verbose_name": "historical stem",
                "verbose_name_plural": "historical stems",
            },
        ),
        migrations.AlterModelOptions(
            name="historicalstemmetadata",
            options={
                "get_latest_by": ("history_date", "history_id"),
                "ordering": ("-history_date", "-history_id"),
                "verbose_name": "historical stem metadata",
                "verbose_name_plural": "historical stem metadatas",
            },
        ),
        migrations.AlterField(
            model_name="historicalaffiliation",
            name="history_date",
            field=models.DateTimeField(db_index=True),
        ),
        migrations.AlterField(
            model_name="historicalexample",
            name="history_date",
            field=models.DateTimeField(db_index=True),
        ),
        migrations.AlterField(
            model_name="historicallexeme",
            name="history_date",
            field=models.DateTimeField(db_index=True),
        ),
        migrations.AlterField(
            model_name="historicallexememetadata",
            name="history_date",
            field=models.DateTimeField(db_index=True),
        ),
        migrations.AlterField(
            model_name="historicallexememetadata",
            name="type",
            field=models.IntegerField(
                blank=True,
                choices=[
                    (0, "Generic"),
                    (1, "Specification"),
                    (3, "Gender"),
                    (4, "Type"),
                    (5, "defNative"),
                    (6, "Ignore"),
                    (7, "Geo"),
                    (8, "MWE"),
                    (9, "MSD"),
                ],
                default=None,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="historicalminiparadigm",
            name="history_date",
            field=models.DateTimeField(db_index=True),
        ),
        migrations.AlterField(
            model_name="historicalrelation",
            name="history_date",
            field=models.DateTimeField(db_index=True),
        ),
        migrations.AlterField(
            model_name="historicalrelationexample",
            name="history_date",
            field=models.DateTimeField(db_index=True),
        ),
        migrations.AlterField(
            model_name="historicalrelationexamplerelation",
            name="history_date",
            field=models.DateTimeField(db_index=True),
        ),
        migrations.AlterField(
            model_name="historicalrelationmetadata",
            name="history_date",
            field=models.DateTimeField(db_index=True),
        ),
        migrations.AlterField(
            model_name="historicalsource",
            name="history_date",
            field=models.DateTimeField(db_index=True),
        ),
        migrations.AlterField(
            model_name="historicalstem",
            name="history_date",
            field=models.DateTimeField(db_index=True),
        ),
        migrations.AlterField(
            model_name="historicalstemmetadata",
            name="history_date",
            field=models.DateTimeField(db_index=True),
        ),
        migrations.AlterField(
            model_name="lexememetadata",
            name="type",
            field=models.IntegerField(
                blank=True,
                choices=[
                    (0, "Generic"),
                    (1, "Specification"),
                    (3, "Gender"),
                    (4, "Type"),
                    (5, "defNative"),
                    (6, "Ignore"),
                    (7, "Geo"),
                    (8, "MWE"),
                    (9, "MSD"),
                ],
                default=None,
                null=True,
            ),
        ),
    ]
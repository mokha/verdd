# Generated by Django 2.2.1 on 2020-01-27 01:10

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import simple_history.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("manageXML", "0012_auto_20200106_1813"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="historicalrelation",
            name="specification",
        ),
        migrations.RemoveField(
            model_name="relation",
            name="specification",
        ),
        migrations.AddField(
            model_name="historicalrelationexample",
            name="language",
            field=models.CharField(default="sms", max_length=3),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="relationexample",
            name="language",
            field=models.CharField(default="sms", max_length=3),
            preserve_default=False,
        ),
        migrations.AlterUniqueTogether(
            name="relationexample",
            unique_together={("relation", "language", "text")},
        ),
        migrations.CreateModel(
            name="HistoricalRelationMetadata",
            fields=[
                (
                    "id",
                    models.IntegerField(
                        auto_created=True, blank=True, db_index=True, verbose_name="ID"
                    ),
                ),
                ("text", models.CharField(max_length=250)),
                ("language", models.CharField(max_length=3)),
                (
                    "type",
                    models.IntegerField(
                        blank=True,
                        choices=[(1, "Specification")],
                        default=None,
                        null=True,
                    ),
                ),
                ("history_id", models.AutoField(primary_key=True, serialize=False)),
                ("history_date", models.DateTimeField()),
                ("history_change_reason", models.CharField(max_length=100, null=True)),
                (
                    "history_type",
                    models.CharField(
                        choices=[("+", "Created"), ("~", "Changed"), ("-", "Deleted")],
                        max_length=1,
                    ),
                ),
                (
                    "changed_by",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "history_user",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "relation",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="manageXML.Relation",
                    ),
                ),
            ],
            options={
                "verbose_name": "historical relation metadata",
                "ordering": ("-history_date", "-history_id"),
                "get_latest_by": "history_date",
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.CreateModel(
            name="RelationMetadata",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("text", models.CharField(max_length=250)),
                ("language", models.CharField(max_length=3)),
                (
                    "type",
                    models.IntegerField(
                        blank=True,
                        choices=[(1, "Specification")],
                        default=None,
                        null=True,
                    ),
                ),
                (
                    "changed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="relation_metadata",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "relation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="manageXML.Relation",
                    ),
                ),
            ],
            options={
                "unique_together": {("relation", "language", "type", "text")},
            },
        ),
    ]

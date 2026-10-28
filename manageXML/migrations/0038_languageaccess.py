from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("manageXML", "0037_alter_affiliation_id_alter_datafile_id_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LanguageAccess",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "language_a",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+", to="manageXML.language"),
                ),
                (
                    "language_b",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+", to="manageXML.language"),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="language_access",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "language access",
                "unique_together": {("user", "language_a", "language_b")},
            },
        ),
    ]

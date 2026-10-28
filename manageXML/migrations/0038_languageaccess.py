from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def mysql_create_sql(quote, table, language_table, user_table, charset, collation):
    """CREATE TABLE for LanguageAccess whose language columns have exactly the character set and
    collation of the language table's key. MySQL/MariaDB refuse a foreign key between string
    columns that differ in either, and Ve'rdd's language table (utf8mb4_bin) does not use the
    database default (utf8mb4_general_ci) that a plain CREATE TABLE would give them."""
    column = "varchar(3)"
    if charset:
        column += " CHARACTER SET %s" % charset
    if collation:
        column += " COLLATE %s" % collation
    q = quote
    return (
        "CREATE TABLE {t} (\n"
        "  {id} integer AUTO_INCREMENT NOT NULL PRIMARY KEY,\n"
        "  {a} {col} NOT NULL,\n"
        "  {b} {col} NOT NULL,\n"
        "  {u} integer NOT NULL,\n"
        "  CONSTRAINT {uniq} UNIQUE ({u}, {a}, {b}),\n"
        "  CONSTRAINT {fk_a} FOREIGN KEY ({a}) REFERENCES {lt} ({id}),\n"
        "  CONSTRAINT {fk_b} FOREIGN KEY ({b}) REFERENCES {lt} ({id}),\n"
        "  CONSTRAINT {fk_u} FOREIGN KEY ({u}) REFERENCES {ut} ({id})\n"
        ")"
    ).format(
        t=q(table),
        lt=q(language_table),
        ut=q(user_table),
        id=q("id"),
        a=q("language_a_id"),
        b=q("language_b_id"),
        u=q("user_id"),
        col=column,
        uniq=q(table + "_user_language_a_language_b_uniq"),
        fk_a=q(table + "_language_a_id_fk"),
        fk_b=q(table + "_language_b_id_fk"),
        fk_u=q(table + "_user_id_fk"),
    )


class CreateLanguageAccess(migrations.CreateModel):
    """CreateModel that, on MySQL/MariaDB, matches the language key's collation (see mysql_create_sql)."""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        connection = schema_editor.connection
        if connection.vendor != "mysql":
            return super().database_forwards(app_label, schema_editor, from_state, to_state)
        model = to_state.apps.get_model(app_label, self.name)
        language_table = to_state.apps.get_model(app_label, "Language")._meta.db_table
        user_table = to_state.apps.get_model(settings.AUTH_USER_MODEL)._meta.db_table
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT CHARACTER_SET_NAME, COLLATION_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = 'id'",
                [language_table],
            )
            row = cursor.fetchone() or (None, None)
        schema_editor.execute(
            mysql_create_sql(
                schema_editor.quote_name, model._meta.db_table, language_table, user_table, row[0], row[1]
            )
        )


class Migration(migrations.Migration):

    dependencies = [
        ("manageXML", "0037_alter_affiliation_id_alter_datafile_id_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        CreateLanguageAccess(
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

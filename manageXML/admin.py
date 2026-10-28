from django.contrib import admin
from .models import *
from simple_history.admin import SimpleHistoryAdmin


class LexemeAdmin(SimpleHistoryAdmin):
    search_fields = (
        "id",
        "lexeme",
        "pos",
    )


class RelationAdmin(SimpleHistoryAdmin):
    search_fields = (
        "id",
        "lexeme_from__lexeme",
        "lexeme_to__lexeme",
    )


admin.site.register(DataFile)
admin.site.register(Lexeme, LexemeAdmin)
admin.site.register(Relation, RelationAdmin)
admin.site.register(Affiliation)
admin.site.register(Example, SimpleHistoryAdmin)
admin.site.register(Source, SimpleHistoryAdmin)


class LanguageAccessAdmin(admin.ModelAdmin):
    """Limit a staff member's API / Workbench access to chosen language pairs. A user with no
    rows here is not limited. Equal languages mean that one language on its own."""

    list_display = ("user", "language_a", "language_b")
    list_filter = ("user",)
    search_fields = ("user__username", "language_a__id", "language_b__id")
    autocomplete_fields = ()


admin.site.register(LanguageAccess, LanguageAccessAdmin)

from django.contrib import admin
from .models import *
from simple_history.admin import SimpleHistoryAdmin


class LexemeAdmin(SimpleHistoryAdmin):
    search_fields = ('id', 'lexeme', 'pos',)


class RelationAdmin(SimpleHistoryAdmin):
    search_fields = ('id', 'lexeme_from', 'lexeme_to',)


admin.site.register(DataFile)
admin.site.register(Lexeme, LexemeAdmin)
admin.site.register(Relation, RelationAdmin)
admin.site.register(Affiliation)
admin.site.register(Examples, SimpleHistoryAdmin)
admin.site.register(Source, SimpleHistoryAdmin)

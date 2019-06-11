from django.contrib import admin
from .models import *
from simple_history.admin import SimpleHistoryAdmin

admin.site.register(DataFile)
admin.site.register(Lexeme, SimpleHistoryAdmin)
admin.site.register(Relation, SimpleHistoryAdmin)
admin.site.register(Affiliation)
admin.site.register(Examples, SimpleHistoryAdmin)
admin.site.register(Source, SimpleHistoryAdmin)

from django.contrib import admin
from .models import *
from simple_history.admin import SimpleHistoryAdmin

admin.site.register(DataFile)
admin.site.register(Element, SimpleHistoryAdmin)
admin.site.register(Translation, SimpleHistoryAdmin)
admin.site.register(Affiliation)
admin.site.register(Stem, SimpleHistoryAdmin)
admin.site.register(Etymon, SimpleHistoryAdmin)
admin.site.register(Source, SimpleHistoryAdmin)

from django.contrib import admin

from .models import Category, Event, OddsHistory, SuggestedEvent

admin.site.register(Category)
admin.site.register(Event)
admin.site.register(OddsHistory)
admin.site.register(SuggestedEvent)

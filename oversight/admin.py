from django.contrib import admin
from django import forms

from .models import *

class OversightPeopleInline(admin.TabularInline):
    model = OversightRelevantPerson
    raw_id_fields = ('topic', 'person')
    verbose_name = "Relevant Person"
    verbose_name_plural = "Relevant Person"
    extra = 1

class OversightBillsInline(admin.TabularInline):
    model = OversightRelevantBill
    raw_id_fields = ('topic', 'bill')
    verbose_name = "Relevant Bill"
    verbose_name_plural = "Relevant Bills"
    extra = 1

class OversightCommitteesInline(admin.TabularInline):
    model = OversightRelevantCommittee
    raw_id_fields = ('topic', 'committee')
    verbose_name = "Relevant Committee"
    verbose_name_plural = "Relevant Committees"
    extra = 1

class OversightTopicAdmin(admin.ModelAdmin):
    list_display = ('slug', 'title', 'created')
    inlines = [OversightPeopleInline, OversightBillsInline, OversightCommitteesInline]
    filter_horizontal = ('related_oversight_topics',)
    ordering = ('-created',)
    def save_model(self, request, obj, form, change):
        # After saving, create events.
        obj.save()
        obj.create_events()

class OversightUpdateAdmin(admin.ModelAdmin):
    list_display = ('title', 'topic', 'created')
    ordering = ('-created',)
    raw_id_fields = ('topic',)
    def save_model(self, request, obj, form, change):
        # After saving, create events on the topic.
        obj.save()
        obj.topic.create_events()
    def delete_model(self, request, obj):
        # After saving, refresh events on the topic.
        topic = obj.topic
        obj.delete()
        topic.create_events()

admin.site.register(OversightTopic, OversightTopicAdmin)
admin.site.register(OversightUpdate, OversightUpdateAdmin)

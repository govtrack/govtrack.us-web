# -*- coding: utf-8

from django.contrib import admin
from committee.models import Committee, Subcommittee

class SubcommitteeInline(admin.TabularInline):
    model = Subcommittee

class CommitteeAdmin(admin.ModelAdmin):
    list_display = ['name', 'committee_type', 'code', 'obsolete']
    list_filter = ['obsolete']
    inlines = [SubcommitteeInline]
    search_fields = ['name', 'code']

class SubcommitteeAdmin(admin.ModelAdmin):
    list_display = ['name', 'committee', 'code']


admin.site.register(Committee, CommitteeAdmin)
admin.site.register(Subcommittee, SubcommitteeAdmin)

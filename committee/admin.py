# -*- coding: utf-8

from django.contrib import admin
from committee.models import Committee, CommitteeMember

class CommitteeInline(admin.TabularInline):
    model = Committee

class CommitteeAdmin(admin.ModelAdmin):
    list_display = ['name', 'committee_type', 'code', 'obsolete', 'committee']
    list_filter = ['obsolete']
    inlines = [CommitteeInline]
    search_fields = ['name', 'code']


class CommitteeMemberAdmin(admin.ModelAdmin):
    list_display = ['person', 'committee', 'role']
    raw_id_fields = ['person']
    search_fields = ['person__firstname', 'person__lastname', 'committee__name']

admin.site.register(Committee, CommitteeAdmin)
admin.site.register(CommitteeMember, CommitteeMemberAdmin)

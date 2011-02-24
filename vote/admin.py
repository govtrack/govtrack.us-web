# -*- coding: utf-8

from django.contrib import admin
from vote.models import Vote, VoteOption, Voter

class VoteOptionInline(admin.TabularInline):
    model = VoteOption

class VoteAdmin(admin.ModelAdmin):
    list_display = ('question' ,'congress', 'session', 'chamber', 'number', 'created')
    inlines = (VoteOptionInline,)

class VoteOptionAdmin(admin.ModelAdmin):
    list_display = ('vote', 'key', 'value')

class VoterAdmin(admin.ModelAdmin):
    list_display = ('vote', 'person', 'option', 'created')

admin.site.register(Vote, VoteAdmin)
admin.site.register(VoteOption, VoteOptionAdmin)
admin.site.register(Voter, VoterAdmin)

# -*- coding: utf-8

from django.contrib import admin
from vote.models import Vote, VoteOption, Voter, VoteSummary

class VoteOptionInline(admin.TabularInline):
    model = VoteOption

class VoteAdmin(admin.ModelAdmin):
    list_display = ('question' ,'congress', 'session', 'chamber', 'number', 'created')
    inlines = (VoteOptionInline,)
    raw_id_fields = ('related_bill', 'related_amendment')

class VoteOptionAdmin(admin.ModelAdmin):
    list_display = ('vote', 'key', 'value')

class VoterAdmin(admin.ModelAdmin):
    list_display = ('vote', 'person', 'option', 'created')

class VoteSummaryAdmin(admin.ModelAdmin):
    list_display = ['created', 'vote']
    raw_id_fields = ['vote']

admin.site.register(Vote, VoteAdmin)
admin.site.register(VoteOption, VoteOptionAdmin)
admin.site.register(Voter, VoterAdmin)
admin.site.register(VoteSummary, VoteSummaryAdmin)

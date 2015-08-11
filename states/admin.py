# -*- coding: utf-8

from django.contrib import admin
from states.models import StateBill, StateSession

class StateBillAdmin(admin.ModelAdmin):
	pass

class StateSessionAdmin(admin.ModelAdmin):
	list_display = ['state', 'startdate', 'enddate', 'name', 'slug', 'current']

admin.site.register(StateBill, StateBillAdmin)
admin.site.register(StateSession, StateSessionAdmin)

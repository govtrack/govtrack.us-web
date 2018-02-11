# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin

from .models import *

class StakeholderAdmin(admin.ModelAdmin):
    list_display = ('slug', 'name', 'verified')
    raw_id_fields = ('admins',)

admin.site.register(Stakeholder, StakeholderAdmin)

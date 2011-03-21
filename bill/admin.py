# -*- coding: utf-8

from django.contrib import admin
from bill.models import BillTerm

class BillTermAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'term_type']


admin.site.register(BillTerm, BillTermAdmin)

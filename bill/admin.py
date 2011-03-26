# -*- coding: utf-8

from django.contrib import admin
from bill.models import BillTerm, Bill

class BillTermAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'term_type']

class BillAdmin(admin.ModelAdmin):
    list_display = ['title', 'congress', 'number']
    raw_id_fields = ['sponsor']


admin.site.register(BillTerm, BillTermAdmin)
admin.site.register(Bill, BillAdmin)

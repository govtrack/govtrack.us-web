# -*- coding: utf-8

from django.contrib import admin
from bill.models import BillTerm, Bill, Cosponsor

class BillTermAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'term_type']
    search_fields = ['name']

class CosponsorInline(admin.TabularInline):
    model = Cosponsor
    extra = 1


class BillAdmin(admin.ModelAdmin):
    list_display = ['title', 'congress', 'number']
    raw_id_fields = ['sponsor']
    inlines = (CosponsorInline,)


admin.site.register(BillTerm, BillTermAdmin)
admin.site.register(Bill, BillAdmin)

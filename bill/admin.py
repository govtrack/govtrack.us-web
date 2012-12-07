# -*- coding: utf-8

from django.contrib import admin
from bill.models import BillTerm, Bill, Cosponsor, BillLink

class BillTermAdmin(admin.ModelAdmin):
    list_display = ['name', 'term_type']
    search_fields = ['name']

class CosponsorInline(admin.TabularInline):
    model = Cosponsor
    extra = 1


class BillAdmin(admin.ModelAdmin):
    list_display = ['title', 'congress', 'number']
    raw_id_fields = ['sponsor', 'cosponsors', 'sponsor_role', 'committees', 'terms']
    inlines = (CosponsorInline,)

class BillLinkAdmin(admin.ModelAdmin):
    list_display = ['created', 'url', 'title', 'approved']
    raw_id_fields = ['bill']
    def make_approved(modeladmin, request, queryset):
        queryset.update(approved=True)
	#make_approved.short_description = "Mark selected links as approved"
    actions = [make_approved]

admin.site.register(BillTerm, BillTermAdmin)
admin.site.register(Bill, BillAdmin)
admin.site.register(BillLink, BillLinkAdmin)


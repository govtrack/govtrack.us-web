# -*- coding: utf-8

from django.contrib import admin
from bill.models import BillTerm, Bill, Cosponsor, BillLink, BillSummary

class BillTermAdmin(admin.ModelAdmin):
    list_display = ['name', 'term_type']
    search_fields = ['name']

class CosponsorInline(admin.TabularInline):
    model = Cosponsor
    extra = 1


class BillAdmin(admin.ModelAdmin):
    list_display = ['title', 'congress', 'introduced_date']
    raw_id_fields = ['sponsor', 'cosponsors', 'sponsor_role', 'committees', 'terms']
    fields = ('congress', 'bill_type', 'number', 'title', 'lock_title', 'sponsor', 'introduced_date', 'source', 'source_link', 'original_intent_replaced', # some field is causing problems
       'sliplawpubpriv', 'sliplawnum' )
    search_fields = ('title', 'congress')
    list_filter = ('congress', 'bill_type', 'current_status')
    ordering = ('-introduced_date', '-congress', '-bill_type', '-number')

class BillLinkAdmin(admin.ModelAdmin):
    list_display = ['created', 'url', 'title', 'approved']
    raw_id_fields = ['bill']
    def make_approved(modeladmin, request, queryset):
        queryset.update(approved=True)
	#make_approved.short_description = "Mark selected links as approved"
    actions = [make_approved]

class BillSummaryAdmin(admin.ModelAdmin):
    list_display = ['created', 'bill']
    raw_id_fields = ['bill']

    def save_model(self, request, obj, form, change):
        obj.save()
        obj.bill.create_events()

        from bill.search_indexes import BillIndex
        bill_index = BillIndex()
        bill_index.update_object(obj.bill, using="bill")
        
    def delete_model(self, request, obj):
    	bill = obj.bill
    	obj.delete()
        bill.create_events()
        
admin.site.register(BillTerm, BillTermAdmin)
admin.site.register(Bill, BillAdmin)
admin.site.register(BillLink, BillLinkAdmin)
admin.site.register(BillSummary, BillSummaryAdmin)


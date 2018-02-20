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
    change_form_template = 'admin/wysiwyg_billsummary_change_form.html' # for django_wysiwyg
    def save_model(self, request, obj, form, change):
        obj.content = BillSummaryAdmin.sanitize_html(obj.content)
        obj.save()
        obj.bill.create_events()

        from bill.search_indexes import BillIndex
        bill_index = BillIndex()
        bill_index.update_object(obj.bill, using="bill")
        
    def delete_model(self, request, obj):
    	bill = obj.bill
    	obj.delete()
        bill.create_events()
        
    @staticmethod
    def sanitize_html(value):
        # based on http://djangosnippets.org/snippets/205/
        from BeautifulSoup import BeautifulSoup
        valid_tags = 'p i strong b u a h1 h2 h3 pre br img ul ol li span'.split()
        valid_attrs = 'href src'.split()
        soup = BeautifulSoup(value)
        for tag in soup.findAll(True):
            if tag.name not in valid_tags:
                tag.hidden = True
            tag.attrs = [(attr, val) for attr, val in tag.attrs
                         if attr in valid_attrs]
        return soup.renderContents().decode('utf8')

admin.site.register(BillTerm, BillTermAdmin)
admin.site.register(Bill, BillAdmin)
admin.site.register(BillLink, BillLinkAdmin)
admin.site.register(BillSummary, BillSummaryAdmin)


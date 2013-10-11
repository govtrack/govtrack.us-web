# -*- coding: utf-8

from django.contrib import admin
from poll_and_call.models import Issue, IssuePosition, RelatedBill, UserPosition

class IssueAdmin(admin.ModelAdmin):
	prepopulated_fields = {"slug": ("title",)}

class RelatedBillAdmin(admin.ModelAdmin):
    raw_id_fields = ['issue', 'bill']

class UserPositionAdmin(admin.ModelAdmin):
    raw_id_fields = ['user', 'position']

admin.site.register(Issue, IssueAdmin)
admin.site.register(IssuePosition)
admin.site.register(RelatedBill, RelatedBillAdmin)
admin.site.register(UserPosition, UserPositionAdmin)

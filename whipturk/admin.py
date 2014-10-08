# -*- coding: utf-8

from django.contrib import admin
from whipturk.models import WhipReport

class WhipReportAdmin(admin.ModelAdmin):
	raw_id_fields = ('bill', 'target', 'user')

admin.site.register(WhipReport, WhipReportAdmin)

# -*- coding: utf-8

from django.contrib import admin
from events.models import *

class SubscriptionListAdmin(admin.ModelAdmin):
    list_display = ['user', 'name', 'email', 'last_email_sent']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['trackers']
    raw_id_fields = ['user']

admin.site.register(SubscriptionList, SubscriptionListAdmin)


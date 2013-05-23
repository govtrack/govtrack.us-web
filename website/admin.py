# -*- coding: utf-8

from django.contrib import admin
from website.models import *

class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['user']

admin.site.register(UserProfile, UserProfileAdmin)


# -*- coding: utf-8

from django.contrib import admin
from website.models import *

class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['user']

class MediumPostAdmin(admin.ModelAdmin):
	list_display = ['published', 'title', 'url']

admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(MediumPost, MediumPostAdmin)


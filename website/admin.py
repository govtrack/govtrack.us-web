# -*- coding: utf-8

from django.contrib import admin
from markdownx.admin import MarkdownxModelAdmin
from website.models import *

class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['user']

class MediumPostAdmin(admin.ModelAdmin):
    list_display = ['published', 'title', 'url']

class BlogPostAdmin(MarkdownxModelAdmin):
    list_display = ['title', 'published', 'created', 'category']
    list_filter = ['category', 'published']
    search_fields = ['title']
    ordering = ('-created',)

admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(MediumPost, MediumPostAdmin)
admin.site.register(Community)
admin.site.register(CommunityMessageBoard)
admin.site.register(CommunityMessage)
admin.site.register(BlogPost, BlogPostAdmin)

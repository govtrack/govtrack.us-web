# -*- coding: utf-8
from django.contrib import admin

from person.models import Person

class PersonAdmin(admin.ModelAdmin):
    list_display = ['name', 'birthday', 'gender', 'title', 'state']

admin.site.register(Person, PersonAdmin)

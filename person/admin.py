# -*- coding: utf-8
from django.contrib import admin

from person.models import Person, PersonRole

class PersonRoleInline(admin.TabularInline):
    model = PersonRole

class PersonAdmin(admin.ModelAdmin):
    list_display = ['name', 'birthday', 'gender', 'bioguideid']
    search_fields = ['id', 'firstname', 'lastname']
    inlines = [PersonRoleInline]

class PersonRoleAdmin(admin.ModelAdmin):
    list_display = ['person', 'role_type', 'startdate', 'enddate', 'current']

admin.site.register(Person, PersonAdmin)
admin.site.register(PersonRole, PersonRoleAdmin)


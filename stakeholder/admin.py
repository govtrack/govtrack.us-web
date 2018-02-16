# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin
from django import forms

from .models import *

class AdminForm(forms.ModelForm):
    class Meta:
        model = Stakeholder.admins.through
        fields = ['user']
    email = forms.CharField(label='Email', disabled=True, required=False)
    date_joined = forms.DateField(label="Date Joined", disabled=True, required=False)
    last_login = forms.DateField(label="Last Login", disabled=True, required=False)
    def __init__(self, *args, **kwargs):
        if "instance" in kwargs:
            kwargs = dict(kwargs) if kwargs else {}
            kwargs.setdefault("initial", {})
            for field in ("email", "date_joined", "last_login"):
                kwargs["initial"][field] = getattr(kwargs["instance"].user, field)
        super(AdminForm, self).__init__(*args, **kwargs)

class StakeholderAdminsInline(admin.TabularInline):
    model = Stakeholder.admins.through
    raw_id_fields = ('stakeholder', 'user')
    verbose_name = "Administrator"
    verbose_name_plural = "Administrators"
    extra = 0
    form = AdminForm

class StakeholderAdmin(admin.ModelAdmin):
    list_display = ('slug', 'name', 'verified')
    list_filter = ('verified',)
    inlines = [StakeholderAdminsInline]
    exclude = ('admins', 'extra')

admin.site.register(Stakeholder, StakeholderAdmin)

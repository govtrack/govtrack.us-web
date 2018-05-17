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
    extra = 1
    form = AdminForm

class StakeholderAdmin(admin.ModelAdmin):
    list_display = ('slug', 'name', 'verified', 'created')
    list_filter = ('verified',)
    inlines = [StakeholderAdminsInline]
    exclude = ('admins', 'extra')
    ordering = ('-created',)

class BillPositionAdminInline(admin.TabularInline):
    model = BillPosition
    raw_id_fields = ('post', 'bill')

class VotePositionAdminInline(admin.TabularInline):
    model = VotePosition
    raw_id_fields = ('post', 'vote')

class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'stakeholder_', 'positions', 'created', 'stakeholder_verified')
    raw_id_fields = ('stakeholder',)
    inlines = [BillPositionAdminInline, VotePositionAdminInline]
    exclude = ('extra',)
    def stakeholder_(self, obj): return obj.stakeholder.name
    def stakeholder_verified(self, obj): return obj.stakeholder.verified
    list_filter = ('stakeholder__verified',)

admin.site.register(Stakeholder, StakeholderAdmin)
admin.site.register(Post, PostAdmin)

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models
from django.conf import settings

from jsonfield import JSONField

import uuid

class Panel(models.Model):
    title = models.CharField(max_length=150, help_text="The display name of the panel, visible to panel members.")
    
    welcome_message = models.TextField(blank=True, help_text="Welcome text to show on invitations.")
    contact_info = models.CharField(max_length=500, help_text="How panel members should contact you with questions.")
    consent_text = models.CharField(max_length=500, help_text="Disclaimer shown to panel members about how information will be used.")

    admins = models.ManyToManyField('auth.User', help_text="The users who own this panel.")
    private_notes = models.TextField(blank=True, help_text="Private notes for the panel owner.")

    extra = JSONField(blank=True, default={}, help_text="Additional information stored with this object.")

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True, db_index=True)

    def get_absolute_url(self):
        return "/panels/" + str(self.id)

class PanelMembership(models.Model):
    panel = models.ForeignKey(Panel, help_text="The panel that the user is a member of.")
    user = models.ForeignKey('auth.User', help_text="The user who is a member of the panel.")

    invitation_code = models.UUIDField(editable=False, help_text="The invitation code used to accept the invitation.")
    extra = JSONField(blank=True, default={}, help_text="Additional information stored with this object.")

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        unique_together = [ ('panel', 'user') ]

class PanelInvitation(models.Model):
    panel = models.ForeignKey(Panel, help_text="The panel that the user is being invited to.")
    code = models.UUIDField(default=uuid.uuid4, editable=False, help_text="The invitation code used in the return URL.")

    extra = JSONField(blank=True, default={}, help_text="Additional information stored with this object.")

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True, db_index=True)

    @property
    def url(self):
        return settings.SITE_ROOT_URL + "/panels/join/" + str(self.code)

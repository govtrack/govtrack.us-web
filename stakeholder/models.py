# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models
from django.conf import settings

from jsonfield import JSONField

import re


class Stakeholder(models.Model):
    verified = models.NullBooleanField(default=None, help_text="Whether this organization has been verified (True), if verification was denied (False), or if verification is pending (None).")

    name = models.CharField(max_length=150, help_text="The display name of the stakeholder.")
    slug = models.SlugField(help_text="The slug used in URLs.")
    
    website = models.URLField(blank=True, null=True)
    twitter_handle = models.CharField(max_length=64, blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    admins = models.ManyToManyField('auth.User', help_text="The users who can manage information about this stakeholder.")

    extra = JSONField(blank=True, default={}, help_text="Additional information stored with this object.")

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True, db_index=True)

    def __str__(self):
        return "<Stakeholder %d %s>" % (self.id, self.slug)

    def get_absolute_url(self):
        return "/stakeholders/" + self.slug + "/" + str(self.id)

    def save(self):
        self.set_slug()
        super(Stakeholder, self).save()

    def set_slug(self):
        # Always match Twitter handle if set.
        if self.twitter_handle:
            self.slug = self.twitter_handle
            return

        # Otherwise keep whatever is set.
        if self.slug:
            return

        # Reset to something generated, first from the website's hostname,
        # minus an initial "www." if present and chopping off .com or .org.
        if self.website:
            import urlparse
            try:
                p = urlparse.urlparse(self.website)
                m = re.match(r"(www\.)?(.*)(\.com|\.org)$", p.hostname)
                self.slug = m.group(2)
                return
            except:
                pass

        # Slugify name.
        from django.utils.text import slugify
        self.slug = slugify(self.name)



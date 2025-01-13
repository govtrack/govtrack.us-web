# -*- coding: utf-8 -*-


from django.db import models
from django.conf import settings

from jsonfield import JSONField

import re

from bill.models import Bill
from vote.models import Vote


class Stakeholder(models.Model):
    verified = models.BooleanField(default=None, null=True, help_text="Whether this organization has been verified (True), if verification was denied (False), or if verification is pending (None).")

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
        if self.verified:
            return self.slug
        else:
            return "[unverified] " + self.slug

    def __repr__(self):
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
            import urllib.parse
            try:
                p = urllib.parse.urlparse(self.website)
                m = re.match(r"(www\.)?(.*)(\.com|\.org)$", p.hostname)
                self.slug = m.group(2)
                return
            except:
                pass

        # Slugify name.
        from django.utils.text import slugify
        self.slug = slugify(self.name)

class Post(models.Model):
    stakeholder = models.ForeignKey(Stakeholder, on_delete=models.CASCADE, help_text="The stakeholder that created this post.")

    post_type = models.IntegerField(choices=[(0, "Positions Only"), (1, "Summary"), (2, "Update")])

    content = models.TextField(blank=True, null=True, help_text="The summary or post text in Markdown format.")
    link = models.URLField(blank=True, null=True)
    
    extra = JSONField(blank=True, default={}, help_text="Additional information stored with this object.")

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True, db_index=True)

    def __str__(self):
        return "<StakeholderPost %d %s>" % (self.id, str(self.stakeholder))

    def title(self):
        if self.content is None:
            ret = self.positions()
            if ret == "": ret = "<no content or positions>"
            return ret
        self.content = self.content.replace("\r\n", "\n").replace("\r", "\n")
        title = self.content
        m = re.match(r"#*.*?(\n\n|$)", self.content.lstrip(), re.S)
        if m: # take first Markdown paragraph
            title = m.group(0).strip()
        title = title.lstrip("#").strip() # remove Markdown heading
        return title

    def positions(self):
        return ", ".join(sorted(str(x) for x in list(self.bill_positions.all()) + list(self.vote_positions.all())))
    def positions_vp(self):
        return ", ".join(sorted(
            ((x.get_position_display().lower() + "s ") if x.position != 0 else "statement on ")
             + str(x.get_target())
            for x in list(self.bill_positions.all()) + list(self.vote_positions.all())
            ))

    def get_a_target_link(self):
        for x in list(self.bill_positions.all()) + list(self.vote_positions.all()):
            return x.get_target().get_absolute_url()
        return None
    def get_thumbnail_url_ex(self):
        for x in self.bill_positions.all():
            return x.bill.get_thumbnail_url_ex()
        return None

class BillPosition(models.Model):
    post = models.ForeignKey(Post, related_name="bill_positions", on_delete=models.CASCADE, help_text="The post that this position is related to.")
    bill = models.ForeignKey(Bill, related_name="stakeholder_positions", on_delete=models.PROTECT, help_text="The bill this position is on.")
    position = models.IntegerField(choices=[(1, "Support"), (0, "Neutral"), (-1, "Oppose")], blank=True, null=True, help_text="The stakeholder's position on the bill: against (-1), neutral/it's complicated (0), 1 (support), or null if the stakeholder is merely providing a summary and has no position.")
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True, db_index=True)
    class Meta:
        unique_together = [('post', 'bill', 'position')]
    def __str__(self): # for admin and Post.positions
        return ((self.get_position_display()+": ") if self.position is not None else "") + str(self.bill)
    def get_target(self):
        return self.bill

class VotePosition(models.Model):
    post = models.ForeignKey(Post, related_name="vote_positions", on_delete=models.CASCADE, help_text="The post that this position is related to.")
    vote = models.ForeignKey(Vote, related_name="stakeholder_positions", on_delete=models.PROTECT, help_text="The vote this position is on.")
    position = models.IntegerField(choices=[(1, "Aye/Yea"), (0, "Neutral"), (-1, "No/Nay")], blank=True, null=True, help_text="The stakeholder's position on the vote: against (-1), neutral/it's complicated (0), 1 (support), or null if the stakeholder is merely providing a summary and has no position.")
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True, db_index=True)
    class Meta:
        unique_together = [('post', 'vote', 'position')]
    def __str__(self): # for admin and Post.positions
        return ((self.get_position_display()+": ") if self.position is not None else "") + str(self.vote)
    def get_target(self):
        return self.vote

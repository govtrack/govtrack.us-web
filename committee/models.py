# -*- coding: utf-8 -*-
from django.db import models

from common import enum

class CommitteeType(enum.Enum):
    senate = enum.Item(1, 'Senat')
    joint = enum.Item(2, 'Joint')
    house = enum.Item(3, 'House')


class Committee(models.Model):
    committee_type = models.IntegerField(choices=CommitteeType)
    code = models.CharField(max_length=5)
    name = models.CharField(max_length=255)
    url = models.CharField(max_length=255, blank=True)
    abbrev = models.CharField(max_length=255, blank=True)
    obsolete = models.BooleanField(blank=True, default=False)

    def __unicode__(self):
        return self.name


class Subcommittee(models.Model):
    committee = models.ForeignKey('committee.Committee')
    code = models.IntegerField()
    name = models.CharField(max_length=255)

    def __unicode__(self):
        return self.name

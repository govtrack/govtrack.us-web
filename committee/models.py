# -*- coding: utf-8 -*-
from django.db import models

from common import enum

class CommitteeType(enum.Enum):
    senate = enum.Item(1, 'Senat')
    joint = enum.Item(2, 'Joint')
    house = enum.Item(3, 'House')


class Committee(models.Model):
    """
    Holds info about committees and subcommittees.

    Subcommittees have only code, name, parent nonblank attributes.
    """

    # committee_type makes sense only for committees
    committee_type = models.IntegerField(choices=CommitteeType, blank=True, null=True)
    code = models.CharField(max_length=5)
    name = models.CharField(max_length=255)
    url = models.CharField(max_length=255, blank=True)
    abbrev = models.CharField(max_length=255, blank=True)
    obsolete = models.BooleanField(blank=True, default=False)
    committee = models.ForeignKey('self', blank=True, null=True, related_name='subcommittees')

    def __unicode__(self):
        return self.name


class CommitteeMemberRole(enum.Enum):
    exofficio = enum.Item(1, 'Ex Officio')
    chairman = enum.Item(2, 'Chairman')
    ranking_member = enum.Item(3, 'Ranking Member')
    vice_chairman = enum.Item(4, 'Vice Chairman')
    member = enum.Item(5, 'Member')

class CommitteeMember(models.Model):
    person = models.ForeignKey('person.Person')
    committee = models.ForeignKey('committee.Committee', related_name='members')
    role = models.IntegerField(choices=CommitteeMemberRole, default=CommitteeMemberRole.member)

    def __unicode__(self):
        return '%s @ %s as %s' % (self.person, self.committee, self.get_role_display())

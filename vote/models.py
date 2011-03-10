# -*- coding: utf-8 -*-
import math

from django.db import models
from django.db.models import Q

from common import enum

class CongressChamber(enum.Enum):
    senate = enum.Item(1, 'Senate')
    house = enum.Item(2, 'House')


class VoteSource(enum.Enum):
    senate = enum.Item(1, 'senate.gov')
    house = enum.Item(2, 'house.gov')
    keithpoole = enum.Item(3, 'keithpoole')


class VoteCategory(enum.Enum):
    amendment = enum.Item(1, 'Amendment')
    passage_suspension = enum.Item(2, 'Passage Suspension')
    passage = enum.Item(3, 'Passage')
    cloture = enum.Item(4, 'Cloture')
    passage_part = enum.Item(5, 'Passage Part')
    nomination = enum.Item(6, 'Nomination')
    procedural = enum.Item(7, 'Procedural')
    other = enum.Item(8, 'Other')


class VoterType(enum.Enum):
    unknown = enum.Item(1, 'Unknown')
    vice_president = enum.Item(2, 'Vice President')
    member = enum.Item(3, 'Member of Congress')


class Vote(models.Model):
    congress = models.IntegerField()
    session = models.CharField(max_length=4)
    chamber = models.IntegerField(choices=CongressChamber)
    number = models.IntegerField('Vote Number')
    source = models.IntegerField(choices=VoteSource)
    created = models.DateTimeField()
    vote_type = models.CharField(max_length=255)
    category = models.CharField(max_length=255, choices=VoteCategory)
    question = models.TextField()
    required = models.CharField(max_length=10)
    result = models.TextField()
    total_plus = models.IntegerField(blank=True, default=0)
    total_minus = models.IntegerField(blank=True, default=0)
    total_other = models.IntegerField(blank=True, default=0)

    def __unicode__(self):
        return self.question

    def calculate_totals(self):
        self.total_plus = self.voters.filter(option__key='+').count()
        self.total_minus = self.voters.filter(option__key='-').count()
        self.total_other = self.voters.count() - (self.total_plus + self.total_minus)
        self.save()

    def totals(self):
        items = []
        total_count = self.voters.count()

        def build_item(option, **kwargs):
            voters = self.voters.filter(option=option)
            count = len(voters)
            #dcount = len(filter(lambda x: 
            percent = math.ceil((count / float(total_count)) * 100)
            res = {'option': option, 'count': count, 'percent': percent}
            res.update(kwargs)
            return res

        for option in self.options.filter(key='+'):
            items.append(build_item(option, yes=True))
        for option in self.options.filter(key='-'):
            items.append(build_item(option, no=True))
        for option in self.options.exclude(Q(key='+') | Q(key='-')):
            items.append(build_item(option))
        return items


class VoteOption(models.Model):
    vote = models.ForeignKey('vote.Vote', related_name='options')
    key = models.CharField(max_length=20)
    value = models.CharField(max_length=255)

    def __unicode__(self):
        return self.value


class Voter(models.Model):
    vote = models.ForeignKey('vote.Vote', related_name='voters')
    person = models.ForeignKey('person.Person', null=True)
    voter_type = models.IntegerField(choices=VoterType)
    option = models.ForeignKey('vote.VoteOption')
    created = models.DateTimeField(db_index=True) # equal to vote.created

    def __unicode__(self):
        return '%s: %s' % (self.person, self.vote)

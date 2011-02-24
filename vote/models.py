# -*- coding: utf-8 -*-
from django.db import models

from common import enum

class CongressChamber(enum.Enum):
    senate = enum.Item(1, 'Senate')
    house = enum.Item(2, 'House')


class VoteSource(enum.Enum):
    senate = enum.Item(1, 'senate.gov')
    house = enum.Item(2, 'house.gov')
    keithpoole = enum.Item(3, 'keithpoole')


class Vote(models.Model):
    congress = models.IntegerField()
    session = models.CharField(max_length=4)
    chamber = models.IntegerField(choices=CongressChamber)
    number = models.IntegerField('Vote Number')
    source = models.IntegerField(choices=VoteSource)
    created = models.DateTimeField()
    vote_type = models.CharField(max_length=255)
    question = models.TextField()
    required = models.CharField(max_length=10)
    result = models.TextField()

    def __unicode__(self):
        return self.question


class VoteOption(models.Model):
    vote = models.ForeignKey('vote.Vote')
    key = models.CharField(max_length=1)
    value = models.CharField(max_length=255)

    def __unicode__(self):
        return '%s: %s' % (self.key, self.value)


class Voter(models.Model):
    vote = models.ForeignKey('vote.Vote')
    person = models.ForeignKey('person.Person')
    option = models.ForeignKey('vote.VoteOption')
    created = models.DateTimeField(db_index=True) # equal to vote.created

    def __unicode__(self):
        return '%s: %s' % (self.person, self.vote)

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

        # Extract all voters, find their role at the time
        # the vote was
        all_voters = list(self.voters.all())
        voters_by_option = {}
        for option in self.options.all():
            voters_by_option[option] = [x for x in all_voters if x.option == option]
        total_count = len(all_voters)
        for voter in all_voters:
            voter.role = voter.person.get_role_at_date(self.created)

        # Find all parties which participated in vote
        # and sort them in order which they should be displayed

        def cmp_party(x):
            """
            Democrats go first, republicans go second.
            Other parties go last.
            """

            if 'demo' in x.lower():
                return 1
            if 'repub' in x.lower():
                return 2
            return 3
        
        all_parties = list(set(x.role.party for x in all_voters))
        all_parties.sort(key=cmp_party)
        total_party_stats = dict((x, {'yes': 0, 'no': 0, 'other': 0, 'total': 0})\
                                 for x in all_parties)

        # For each option find party break down,
        # total vote count and percentage in total count
        details = []
        for option in self.options.all():
            voters = voters_by_option.get(option, [])
            percent = math.ceil((len(voters) / float(total_count)) * 100)
            party_stats = dict((x, 0) for x in all_parties)
            for voter in voters:
                party_stats[voter.role.party] += 1
                total_party_stats[voter.role.party]['total'] += 1
                if option.key == '+':
                    total_party_stats[voter.role.party]['yes'] += 1
                elif option.key == '-':
                    total_party_stats[voter.role.party]['no'] += 1
                else:
                    total_party_stats[voter.role.party]['other'] += 1
            party_counts = [party_stats.get(x, 0) for x in all_parties]
                
            detail = {'option': option, 'count': len(voters),
                      'percent': percent, 'party_counts': party_counts}
            if option.key == '+':
                detail['yes'] = True
            if option.key == '-':
                detail['no'] = True
            details.append(detail)

        party_counts = [total_party_stats[x] for x in all_parties]

        return {'options': details, 'total_count': total_count,
                'party_counts': party_counts, 'parties': all_parties,
                }


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

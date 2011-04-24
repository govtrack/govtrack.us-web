# -*- coding: utf-8 -*-
import math

from django.db import models
from django.db.models import Q
from django.core.urlresolvers import reverse

from common import enum

from person.util import load_roles_at_date

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

    def get_absolute_url(self):
        if self.chamber == CongressChamber.house:
            chamber_code = 'h'
        else:
            chamber_code = 's'
        return reverse('vote_details', args=[self.congress, self.session,
                       chamber_code, self.number])
        
    def name(self):
        return CongressChamber.by_value(self.chamber).label + " Vote #" + str(self.number)

    def totals(self):
        # If cached value exists then return it
        if hasattr(self, '_cached_totals'):
            return self._cached_totals
        # else do all these things:

        items = []

        # Extract all voters, find their role at the time
        # the vote was
        all_voters = list(self.voters.all().select_related('person', 'option'))
        voters_by_option = {}
        for option in self.options.all():
            voters_by_option[option] = [x for x in all_voters if x.option == option]
        total_count = len(all_voters)

        persons = [x.person for x in all_voters]
        load_roles_at_date(persons, self.created)

        # Find all parties which participated in vote
        # and sort them in order which they should be displayed

        def cmp_party(x):
            """
            Sort the parties by the number of voters in that party.
            """
            return -len([p for p in all_voters if p.person.role.party == x])
        
        all_parties = list(set(x.person.role.party for x in all_voters))
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
                party_stats[voter.person.role.party] += 1
                total_party_stats[voter.person.role.party]['total'] += 1
                if option.key == '+':
                    total_party_stats[voter.person.role.party]['yes'] += 1
                elif option.key == '-':
                    total_party_stats[voter.person.role.party]['no'] += 1
                else:
                    total_party_stats[voter.person.role.party]['other'] += 1
            party_counts = [party_stats.get(x, 0) for x in all_parties]
                
            detail = {'option': option, 'count': len(voters),
                      'percent': percent, 'party_counts': party_counts}
            if option.key == '+':
                detail['yes'] = True
            if option.key == '-':
                detail['no'] = True
            details.append(detail)

        party_counts = [total_party_stats[x] for x in all_parties]

        totals = {'options': details, 'total_count': total_count,
                'party_counts': party_counts, 'parties': all_parties,
                }
        self._cached_totals = totals
        return totals

    def summary(self):
        return self.result + " " + str(self.total_plus) + "/" + str(self.total_minus)

    def create_event(self):
        from events.feeds import AllVotesFeed, PersonVotesFeed
        from events.models import Event
        with Event.update(self) as E:
            E.add("vote", self.created, AllVotesFeed())
            for v in self.voters.all():
                E.add("vote", self.created, PersonVotesFeed(v.person_id))
	
    def render_event(self, eventid, feeds):
        import events.feeds
        return {
            "type": "Vote",
            "date": self.created,
            "title": self.question,
			"url": self.get_absolute_url(),
            "body_text_template":
"""{{summary|safe}}
{% for voter in voters %}
    {{voter.name|safe}}: {{voter.vote|safe}}
{% endfor %}""",
            "body_html_template":
"""<p>{{summary}}</p>
{% for voter in voters %}
    {% if forloop.first %}<ul>{% endif %}
    <p><a href="{{voter.url}}">{{voter.name}}</a>: {{voter.vote}}</p>
    {% if forloop.last %}</ul>{% endif %}
{% endfor %}
""",
            "context": {
                "summary": self.summary(),
                "voters":
                            [
                                { "url": f.person().get_absolute_url(), "name": f.person().name, "vote": self.voters.get(person=f.person()).option.value }
                                for f in feeds if isinstance(f, events.feeds.PersonFeed) and self.voters.filter(person=f.person()).exists()
                            ]
                        if feeds != None else []
                }
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

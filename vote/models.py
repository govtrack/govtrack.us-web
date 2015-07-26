# -*- coding: utf-8 -*-
import math

from django.db import models
from django.db.models import Q
from django.core.urlresolvers import reverse
from django.conf import settings

from common import enum

from person.util import load_roles_at_date

from us import get_session_ordinal

from decimal import *

import markdown2

class CongressChamber(enum.Enum):
    senate = enum.Item(1, 'Senate')
    house = enum.Item(2, 'House')


class VoteSource(enum.Enum):
    senate = enum.Item(1, 'senate.gov')
    house = enum.Item(2, 'house.gov')
    keithpoole = enum.Item(3, 'Professor Keith Poole')


class VoteCategory(enum.Enum):
    amendment = enum.Item(1, 'Amendment', search_help_text="Votes on accepting or rejecting amendments to bills and resolutions.")
    passage_suspension = enum.Item(2, 'Passage under Suspension', search_help_text="Fast-tracked votes on the passage of bills requiring a 2/3rds majority.")
    passage = enum.Item(3, 'Passage', search_help_text="Votes on passing or failing bills and resolutions and on agreeing to conference reports.")
    cloture = enum.Item(4, 'Cloture', search_help_text="Votes to end debate and move to a vote, i.e. to end a filibuster.")
    passage_part = enum.Item(5, 'Passage (Part)', search_help_text="Votes on the passage of parts of legislation.")
    nomination = enum.Item(6, 'Nomination', search_help_text="Senate votes on presidential nominations.")
    procedural = enum.Item(7, 'Procedural', search_help_text="A variety of procedural votes such as quorum calls.")
    other = enum.Item(8, 'Other', search_help_text="A variety of uncategorized votes.")
    unknown = enum.Item(9, 'Unknown Category', search_help_text="A variety of uncategorized votes.")
    ratification = enum.Item(12, 'Treaty Ratification', search_help_text="Senate votes to ratify treaties.")
    veto_override = enum.Item(10, 'Veto Override', search_help_text="Votes to override a presidential veto.")
    conviction = enum.Item(11, 'Impeachment Conviction', search_help_text="'Guilty or Not Guilty' votes in the Senate to convict an office holder of impeachment.")

class VoterType(enum.Enum):
    unknown = enum.Item(1, 'Unknown')
    vice_president = enum.Item(2, 'Vice President')
    member = enum.Item(3, 'Member of Congress')


class Vote(models.Model):
    """Roll call votes in the U.S. Congress since 1789. How people voted is accessed through the Vote_voter API."""
    
    congress = models.IntegerField(help_text="The number of the Congress in which the vote took place. The current Congress is %d. In recent history Congresses are two years; however, this was not always the case." % settings.CURRENT_CONGRESS)
    session = models.CharField(max_length=4, help_text="Within each Congress there are sessions. In recent history the sessions correspond to calendar years and are named accordingly. However, in historical data the sessions may be named in completely other ways, such as with letters A, B, and C. Session names are unique *within* a Congress.")
    chamber = models.IntegerField(choices=CongressChamber, help_text="The chamber in which the vote was held, House or Senate.")
    number = models.IntegerField('Vote Number', help_text="The number of the vote, unique to a Congress, session, and chamber.")
    source = models.IntegerField(choices=VoteSource, help_text="The source of the vote information.")
    created = models.DateTimeField(db_index=True, help_text="The date (and in recent history also time) on which the vote was held.")
    vote_type = models.CharField(max_length=255, help_text="Descriptive text for the type of the vote.")
    category = models.IntegerField(max_length=255, choices=VoteCategory, help_text="The type of the vote.")
    question = models.TextField(help_text="Descriptive text for what the vote was about.")
    required = models.CharField(max_length=10, help_text="A code indicating what number of votes was required for success. Often '1/2' or '3/5'. This field should be interpreted with care. It comes directly from the upstream source and may need some 'unpacking.' For instance, while 1/2 always mean 1/2 of those voting (i.e. excluding absent and abstain), 3/5 in some cases means to include absent/abstain and in other cases to exclude.")
    result = models.TextField(help_text="Descriptive text for the result of the vote.")
    total_plus = models.IntegerField(blank=True, default=0, help_text="The count of positive votes (aye/yea).")
    total_minus = models.IntegerField(blank=True, default=0, help_text="The count of negative votes (nay/no).")
    total_other = models.IntegerField(blank=True, default=0, help_text="The count of abstain or absent voters.")
    percent_yes = models.DecimalField(blank=True, default=0, decimal_places=2, max_digits=4, help_text="The percent of yes votes.")

    related_bill = models.ForeignKey('bill.Bill', related_name='votes', blank=True, null=True, help_text="A related bill.", on_delete=models.PROTECT)
    related_amendment = models.ForeignKey('bill.Amendment', related_name='votes', blank=True, null=True, help_text="A related amendment.", on_delete=models.PROTECT)
    missing_data = models.BooleanField(default=False, help_text="If something in the source could be parsed and we should revisit the file.")
    question_details = models.TextField(help_text="Additional descriptive text for what the vote was about.", blank=True, null=True)
    
    class Meta:
        # The ordering makes sure votes are in the right order on bill pages.
        ordering = ["created", "chamber", "number"]
        unique_together = (('congress', 'chamber', 'session', 'number'),)

    MAJOR_CATEGORIES = (VoteCategory.passage_suspension, VoteCategory.passage, VoteCategory.passage_part, VoteCategory.nomination, VoteCategory.ratification, VoteCategory.veto_override)
        
    api_additional_fields = {
        "link": lambda obj : settings.SITE_ROOT_URL + obj.get_absolute_url(),
    }
    api_recurse_on = ('related_bill', 'options')
    api_example_parameters = { "sort": "-created" }

    def __unicode__(self):
        return self.question

    def calculate_totals(self):
        self.total_plus = self.voters.filter(option__key='+').count()
        self.total_minus = self.voters.filter(option__key='-').count()
        self.total_other = self.voters.count() - (self.total_plus + self.total_minus)
        self.percent_yes = self.voters.filter(option__key='+').count()/Decimal(self.total_plus + self.total_minus + self.total_other)
        self.save()

    def get_absolute_url(self):
        if self.chamber == CongressChamber.house:
            chamber_code = 'h'
        else:
            chamber_code = 's'
        return reverse('vote_details', args=[self.congress, self.session,
                       chamber_code, self.number])
        
    def get_source_link(self):
        """A link to the website where this vote information was obtained."""
        if self.source == VoteSource.senate:
            return "http://www.senate.gov/legislative/LIS/roll_call_lists/roll_call_vote_cfm.cfm?congress=%d&session=%s&vote=%05d" % (self.congress, get_session_ordinal(self.congress, self.session), self.number)
        elif self.source == VoteSource.house:
            return "http://clerk.house.gov/evs/%d/roll%03d.xml" % (self.created.year, self.number)
        elif self.source == VoteSource.keithpoole:
            return "http://voteview.com/"
        raise ValueError("invalid source: " + str(self.source))
        
    def name(self):
        return CongressChamber.by_value(self.chamber).label + " Vote #" + str(self.number)
        
    @property
    def is_major(self):
        return (self.category in Vote.MAJOR_CATEGORIES) or self.congress <= 42

    @property
    def is_on_passage(self):
        return self.category in (VoteCategory.passage_suspension, VoteCategory.passage)
        
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

        persons = [x.person for x in all_voters if x.person != None]
        load_roles_at_date(persons, self.created)

        # Find all parties which participated in vote
        # and sort them in order which they should be displayed

        def cmp_party(x):
            """
            Sort the parties by the number of voters in that party.
            """
            return -len([p for p in all_voters if p.person and p.person.role and p.person.role.party == x])
        
        def get_party(voter):
            if voter.voter_type != VoterType.vice_president:
                if voter.person and voter.person.role:
                    return voter.person.role.party
                else:
                    return "Unknown"
            else:
                return "Vice President"
        
        all_parties = list(set(get_party(x) for x in all_voters))
        all_parties.sort(key=cmp_party)
        total_party_stats = dict((x, {'yes': 0, 'no': 0, 'other': 0, 'total': 0})\
                                 for x in all_parties)

        # For each option find party break down,
        # total vote count and percentage in total count
        details = []
        for option in self.options.all():
            voters = voters_by_option.get(option, [])
            percent = round(len(voters) / float(total_count) * 100.0)
            party_stats = dict((x, 0) for x in all_parties)
            for voter in voters:
                party = get_party(voter)
                party_stats[party] += 1
                total_party_stats[party]['total'] += 1
                if option.key == '+':
                    total_party_stats[party]['yes'] += 1
                elif option.key == '-':
                    total_party_stats[party]['no'] += 1
                else:
                    total_party_stats[party]['other'] += 1
            party_counts = [party_stats.get(x, 0) for x in all_parties]
            party_counts = [{"party": all_parties[i], "count": c, 'chart_width': 190 * c / total_count} for i, c in enumerate(party_counts)]
                
            detail = {'option': option, 'count': len(voters),
                'percent': int(percent), 'party_counts': party_counts,
                'chart_width': 190 * int(percent) / 100}
            if option.key == '+':
                detail['yes'] = True
            if option.key == '-':
                detail['no'] = True
            if option.key in ('0', 'P'):
                detail['hide_if_empty'] = True
            details.append(detail)

        party_counts = [total_party_stats[x] for x in all_parties]
        
        # sort options by well-known keys, then by total number of votes
        option_sort_order = {"+":0, "-":1, "P":2, "0":3}
        details.sort(key = lambda d : (option_sort_order.get(d['option'].key, None), -d['count']))
        
        # hide Present/Not Voting if no one voted that way
        details = [d for d in details if d["count"] > 0 or "hide_if_empty" not in d]

        totals = {'options': details, 'total_count': total_count,
                'party_counts': party_counts, 'parties': all_parties,
                }
        self._cached_totals = totals
        return totals

    def summary(self):
        return self.result + " " + str(self.total_plus) + "/" + str(self.total_minus)
        
    def simple_record(self):
        # load people and their roles
        all_voters = list(self.voters.all().select_related('person', 'option'))
        persons = [x.person for x in all_voters if x.person != None]
        load_roles_at_date(persons, self.created)

        return [
            { "vote": v.option.value, "moc": v.person.role.simple_record() }
            for v in all_voters
            if v.voter_type_is_member and v.person is not None and v.person.role is not None
        ]

    @staticmethod
    def AllVotesFeed():
        from events.models import Feed
        return Feed.get_noarg_feed("misc:allvotes")
      
    def create_event(self):
        if self.congress < 111: return # not interested, creates too much useless data and slow to load
        from events.models import Feed, Event
        with Event.update(self) as E:
            E.add("vote", self.created, Vote.AllVotesFeed())
            for v in self.voters.all():
                if v.person_id:
                    E.add("vote", self.created, v.person.get_feed("pv"))
    
    def render_event(self, eventid, feeds):
        if feeds:
            from person.models import Person
            my_reps = set()
            for f in feeds:
                try:
                    my_reps.add(Person.from_feed(f))
                except ValueError:
                    pass # not a person-related feed
            my_reps = sorted(my_reps, key = lambda p : p.sortname)
        else:
            my_reps = []

        try:
            oursummary = self.oursummary
        except VoteSummary.DoesNotExist:
            oursummary = None
        
        return {
            "type": "Vote",
            "date": self.created,
            "title": self.question,
            "url": self.get_absolute_url(),
            "body_text_template":
"""{{summary|safe}}
{% for voter in voters %}{{voter.name|safe}}: {{voter.vote|safe}}
{% endfor %}
{% if oursummary %}{{oursummary.plain_text|safe}}{% endif %}""",
            "body_html_template":
"""<p>{{summary}}</p>
{% for voter in voters %}
    <p><a href="{{SITE_ROOT}}{{voter.url}}">{{voter.name}}</a>: {{voter.vote}}</p>
{% endfor %}
{% if oursummary %}{{oursummary.as_html|safe}}{% endif %}
""",
            "context": {
                "summary": self.summary(),
                "oursummary": oursummary,
                "voters":
                            [
                                { "url": p.get_absolute_url(), "name": p.name_lastonly(), "vote": self.voters.get(person=p).option.value }
                                for p in my_reps if self.voters.filter(person=p).exists()
                            ]
                        if feeds != None else []
                }
            }
            
    def possible_reconsideration_votes(self, voters=None):
        # Identify possible voters who voted against their view in order to be on the winning
        # side so they may make a motion to reconsider later. Senate only. Since we don't
        # know which option represents the winning option, we just look at party leaders who
        # voted against their party.
        if self.chamber != CongressChamber.senate: return []

        # Get vote totals by party.
        if voters == None:
            voters = list(self.voters.all().select_related('person', 'option'))
            load_roles_at_date([x.person for x in voters if x.person != None], vote.created)
        by_party = { }
        for voter in voters:
            if not voter.person or not voter.person.role: continue
            if voter.option.key not in ("+", "-"): continue
            by_party.setdefault(voter.person.role.party, {}).setdefault(voter.option_id, set()).add(voter)

        # Find the plurality option by party.
        for party in by_party:
            by_party[party] = max(by_party[party], key = lambda x : len(by_party[party][x]))
    
        # See if any party leaders voted against their party.
        candidates = []
        for voter in voters:
            if voter.person and voter.person.role and voter.person.role.leadership_title:
                if voter.option.key in ("+", "-") and voter.option_id != by_party[voter.person.role.party]:
                    candidates.append(voter)
        return candidates


class VoteOption(models.Model):
    vote = models.ForeignKey('vote.Vote', related_name='options')
    key = models.CharField(max_length=20)
    value = models.CharField(max_length=255)

    def __unicode__(self):
        return self.value
        
    @property
    def alpha_key(self):
        if self.key == "+": return "positive"
        if self.key == "-": return "negative"
        if self.key == "0": return "absent"
        if self.key == "present": return "present"
        return "other"

class Voter(models.Model):
    """How people voted on roll call votes in the U.S. Congress since 1789. See the Vote API. Filter on the vote field to get the results of a particular vote."""
	
    vote = models.ForeignKey('vote.Vote', related_name='voters', help_text="The vote that this record is a part of.")
    person = models.ForeignKey('person.Person', blank=True, null=True, on_delete=models.PROTECT, related_name='votes', help_text="The person who cast this vote. May be null if the information could not be determined.")
    person_role = models.ForeignKey('person.PersonRole', blank=True, null=True, on_delete=models.PROTECT, related_name='votes', help_text="The role of the person who cast this vote at the time of the vote. May be null if the information could not be determined.")
    voter_type = models.IntegerField(choices=VoterType, help_text="Whether the voter was a Member of Congress or the Vice President.")
    option = models.ForeignKey('vote.VoteOption', help_text="How the person voted.")
    created = models.DateTimeField(db_index=True, help_text="The date (and in recent history also time) on which the vote was held.") # equal to vote.created
    
    api_recurse_on = ('vote', 'person', 'person_role', 'option')
    api_example_parameters = { "sort": "-created" }
    api_filter_if = { "option__key": ["person"] }
    
    def __unicode__(self):
        return u'%s /%s/ %s' % (unicode(self.person), self.option.key, unicode(self.vote))
        
    def voter_type_is_member(self):
        return self.voter_type == VoterType.member
        
    def get_option_key(self):
        """Returns the way this person voted. The value corresponds to the key of an option on the vote object."""
        return self.option.key
        
    def person_name(self):
        """The name of the voter."""
        return self.person.name if self.person else None
    
    def get_vote_name(self):
        return self.vote.name()


# Summaries
class VoteSummary(models.Model):
    vote = models.OneToOneField(Vote, related_name="oursummary", on_delete=models.PROTECT)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    content = models.TextField(blank=True)

    def __str__(self): return "Summary for " + str(self.vote)
    def get_absolute_url(self): return self.vote.get_absolute_url()

    def as_html(self):
        return markdown2.markdown(self.content)

    def plain_text(self):
        # Kill links.
        import re
        content = re.sub("\[(.*?)\]\(.*?\)", r"\1", self.content)
        return content

# Feeds
from events.models import Feed
Feed.register_feed(
    "misc:allvotes",
    title = "Roll Call Votes",
    link = "/congress/votes",
    simple = True,
    single_event_type = True,
    sort_order = 101,
    category = "federal-votes",
    description = "You will get an alert for every roll call vote in Congress.",
    )

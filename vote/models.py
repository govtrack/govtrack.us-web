# -*- coding: utf-8 -*-
import math

from django.db import models
from django.db.models import Q, F
from django.urls import reverse
from django.conf import settings

from common import enum

from us import get_session_ordinal
from bill.models import BillSummary

from website.templatetags.govtrack_utils import markdown


# Define U.S. Census Regions
# https://www2.census.gov/geo/pdfs/maps-data/maps/reference/us_regdiv.pdf
census_regions = {
  "Northeast": { "CT", "ME", "MA", "NH", "RI", "VT", "NJ", "NY", "PA" },
  "Midwest": { "IN", "IL", "MI", "OH", "WI", "IA", "KS", "MN", "MO", "NE", "ND", "SD" },
  "South": { "DE", "DC", "FL", "GA", "MD", "NC", "SC", "VA", "WV", "AL", "KY", "MS", "TN", "AR", "LA", "OK", "TX "},
  "West": { "AZ", "CO", "ID", "NM", "MT", "UT", "NV", "WY", "AK", "CA", "HI", "OR", "WA" },
}


global historical_state_population_data
historical_state_population_data = None
def get_state_population_in_year(year):
    # Load historical population by state.
    global historical_state_population_data
    if historical_state_population_data is None:
        import csv
        historical_state_population_data = { }
        for state, row_year, pop in csv.reader(open("analysis/historical_state_population_by_year.csv")):
            historical_state_population_data[(state, int(row_year))] = int(pop)

    # Clamp the year to the max year in the data, since the data lags real time.
    year = min(year, max(y for _, y in historical_state_population_data.keys()))

    return { state: pop for (state, year), pop in historical_state_population_data.items() }


class CongressChamber(enum.Enum):
    senate = enum.Item(1, 'Senate')
    house = enum.Item(2, 'House')


class VoteSource(enum.Enum):
    senate = enum.Item(1, 'senate.gov')
    house = enum.Item(2, 'house.gov')
    keithpoole = enum.Item(3, 'VoteView.com')


class VoteCategory(enum.Enum):
    amendment = enum.Item(1, 'Amendment', search_help_text="Votes on accepting or rejecting amendments to bills and resolutions.", importance=5)
    passage_suspension = enum.Item(2, 'Passage under Suspension', search_help_text="Fast-tracked votes on the passage of bills requiring a 2/3rds majority.", importance=4)
    passage = enum.Item(3, 'Passage', search_help_text="Votes on passing or failing bills and resolutions and on agreeing to conference reports.", importance=3)
    cloture = enum.Item(4, 'Cloture', search_help_text="Votes to end debate and move to a vote, i.e. to end a filibuster.", importance=4)
    passage_part = enum.Item(5, 'Passage (Part)', search_help_text="Votes on the passage of parts of legislation.", importance=3)
    nomination = enum.Item(6, 'Nomination', search_help_text="Senate votes on presidential nominations.", importance=2)
    procedural = enum.Item(7, 'Procedural', search_help_text="A variety of procedural votes such as quorum calls.", importance=6)
    unknown = enum.Item(9, 'Unknown Category', search_help_text="A variety of uncategorized votes.", importance=8)
    ratification = enum.Item(12, 'Treaty Ratification', search_help_text="Senate votes to ratify treaties.", importance=2)
    veto_override = enum.Item(10, 'Veto Override', search_help_text="Votes to override a presidential veto.", importance=1)
    conviction = enum.Item(11, 'Conviction', search_help_text="'Guilty or Not Guilty' votes in the Senate to convict an office holder following impeachment.", importance=1)
    impeachment = enum.Item(13, 'Impeachment', search_help_text="A vote in the House on whether or not to impeach an office-holder.", importance=1)

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
    category = models.IntegerField(choices=VoteCategory, help_text="The type of the vote.")
    question = models.TextField(help_text="Descriptive text for what the vote was about.")
    required = models.CharField(max_length=10, help_text="A code indicating what number of votes was required for success. Often '1/2' or '3/5'. This field should be interpreted with care. It comes directly from the upstream source and may need some 'unpacking.' For instance, while 1/2 always mean 1/2 of those voting (i.e. excluding absent and abstain), 3/5 in some cases means to include absent/abstain and in other cases to exclude.")
    result = models.TextField(help_text="Descriptive text for the result of the vote.")
    passed = models.BooleanField(null=True, help_text="Whether the vote passed or failed, for votes that have such an option. Otherwise None.")

    total_plus = models.IntegerField(blank=True, default=0, help_text="The count of positive votes (aye/yea).")
    total_minus = models.IntegerField(blank=True, default=0, help_text="The count of negative votes (nay/no).")
    total_other = models.IntegerField(blank=True, default=0, help_text="The count of abstain or absent voters.")
    percent_plus = models.FloatField(blank=True, null=True, help_text="The percent of positive votes. Null for votes that aren't yes/no (like election of the speaker, quorum calls).")
    margin = models.FloatField(blank=True, null=True, help_text="The absolute value of the difference in the percent of positive votes and negative votes. Null for votes that aren't yes/no (like election of the speaker, quorum calls).")
    majority_party_percent_plus = models.FloatField(blank=True, null=True, help_text="The percent of positive votes among the majority party only. Null for votes that aren't yes/no (like election of the speaker, quorum calls).")
    party_uniformity = models.FloatField(blank=True, null=True, help_text="A party uniformity score based on the percent of each party voting yes. Null for votes that aren't yes/no (like election of the speaker, quorum calls).")

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

    def __str__(self):
        return self.question

    @property
    def congressproject_id(self):
        return "{chamber}{number}-{congress}.{session}".format(chamber="s" if self.chamber == CongressChamber.senate else "h",
            number=self.number, congress=self.congress, session=self.session)

    @staticmethod
    def from_congressproject_id(s):
        import re
        try:
            m = re.match(r"(h|s)(\d+)-(\d+)\.(\w+)$", s.lower())
            return Vote.objects.get(congress=m.group(3), session=m.group(4), chamber=CongressChamber.senate if m.group(1) == "s" else CongressChamber.house, number=m.group(2))
        except:
            raise Vote.DoesNotExist(s)

    def calculate_totals(self):
        # totals by yes/no/other
        self.total_plus = self.voters.filter(option__key='+').count()
        self.total_minus = self.voters.filter(option__key='-').count()
        self.total_other = self.voters.count() - (self.total_plus + self.total_minus)

        # margin, percent of yes votes
        if self.total_plus + self.total_minus == 0:
            self.percent_plus = None
            self.margin = None
        else:
            self.percent_plus = self.total_plus/float(self.total_plus + self.total_minus + self.total_other)
            self.margin = abs(self.total_plus - self.total_minus) / float(self.total_plus + self.total_minus)

        totals = self.totals(include_features=False)

        if self.total_plus > 0:
            # how did the majority party vote?
            majority_party_votes = totals['party_counts'][0] # first party is the one with the most voters
            self.majority_party_percent_plus = majority_party_votes['yes']/majority_party_votes['total']

            # how uniform were the parties?
            # Sum the count-weighted uniformity scores for all of the parties, and for each party score uniformity
            # as a sin-smoothed distance from a 50% split.
            import math
            self.party_uniformity = sum([
              math.sin(abs(pt['yes']/pt['total'] - .5) * math.pi)
                * pt['total'] / totals["total_count"]
              for pt in totals["party_counts"] ])
        else:
            self.majority_party_percent_plus = None
            self.party_uniformity = None

        # pass or failed?
        import re
        regexes = [
            (True, re.compile(r"Not Sustained")), # the sustained/not sustained cases are awkward to assign to a binary outcome but this seems to make the most sense
            (False, re.compile(r"Failed|Rejected|Defeated|Not Germane|Not Guilty|Sustained")),
            (True, re.compile(r"Passed|Agreed to|Overridden|Confirmed|Ratified|Guilty|Germane|Adopted|Accepted|Not Well Taken")),
            (None, re.compile('.')), # some votes like votes for Speaker or quorum calls do not have a binary outcome
        ]
        for value, regex in regexes:
            if regex.search(self.result):
                self.passed = value
                break
        else:
            raise ValueError("No regex matched for result {}.".format(self.result))

        # which option was the winner? some results match an option text exactly, like votes for Speaker
        winning_option = self.options.filter(value=self.result).first()
        if self.required == "QUORUM":
            if self.result == "Passed":
                winning_option = self.options.get(key="P")
            elif self.result == "Failed":
                winning_option = self.options.get(key="0")
        elif winning_option is None and self.passed is not None and self.options.filter(key__in=("+", "-")).exists():
            # If there's no match and the vote has +/- options and we determined
            # the vote passed or failed, then a passed vote is + and a failed vote is -.
            # Some failed votes don't have a '-' option because everyone voted present,
            # and in that case we need to add an option. But then we have to set the
            # right text value to Nay or No depending on the Yes text. There are also
            # failed votes without '+' options, so we can't assume '+' exists, but only
            # if there is no '-'.
            if self.passed:
                winning_option = self.options.get(key="+")
            else:
                try:
                    winning_option = self.options.get(key="-")
                except VoteOption.DoesNotExist:
                    winning_option = self.options.create(key="-", value="No" if self.options.get(key="+").value == "Aye" else "Nay")
        if winning_option is not None and not winning_option.winner:
            # Winner is known. Set its winner field to true and the other options to false.
            self.options.update(winner=False)
            winning_option.winner = True
            winning_option.save()
        else:
            # No winner known.
            self.options.update(winner=None)

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
            return "https://clerk.house.gov/Votes/{}{}".format(self.created.year, self.number)
        elif self.source == VoteSource.keithpoole:
            return "http://voteview.com/"
        raise ValueError("invalid source: " + str(self.source))

    @property
    def chamber_name(self):
        return CongressChamber.by_value(self.chamber).label
        
    def name(self):
        return self.chamber_name + " Vote #" + str(self.number)
        
    @property
    def is_major(self):
        return (self.category in Vote.MAJOR_CATEGORIES) or self.congress <= 42

    @property
    def is_on_passage(self):
        return self.category in (VoteCategory.passage_suspension, VoteCategory.passage, VoteCategory.veto_override)

    def has_time(self):
        return self.source != VoteSource.keithpoole

    def get_voters(self, filter_people=None):
        # Fetch from database.
        voters = self.voters.all()
        if filter_people: voters = voters.filter(person__in=filter_people)
        ret = list(voters.select_related('person', 'person_role', 'option'))

        # Add the exact party of the person at this time.
        for voter in ret:
            if voter.voter_type == VoterType.vice_president:
                voter.party = "Vice President"
            elif not voter.person or not voter.person_role:
                voter.party = "Unknown"
            else:
                voter.party = voter.person_role.get_party_on_date(self.created, caucus=True)
                voter.party_is_caucus = voter.party != voter.person_role.get_party_on_date(self.created, caucus=False)

        return ret
       
    def totals(self, include_features=True):
        # If cached value exists then return it
        if hasattr(self, '_cached_totals'):
            return self._cached_totals
        # else do all these things:

        items = []

        # Extract all voters.
        all_voters = self.get_voters()
        all_options = list(self.options.all())
        voters_by_option = {}
        for option in all_options:
            voters_by_option[option] = [x for x in all_voters if x.option == option]
        total_count = len(all_voters)
        party_is_caucus = any(getattr(x, "party_is_caucus", False) for x in all_voters)

        # How many legislators count toward or against passage? For most votes, only ayes
        # and nays count toward a majority (i.e. present and not voting don't), or special
        # votes like the name of a legislator in an election for speaker. However, Senate
        # cloture votes require "3/5ths of senators duly sworn" or something, meaning,
        # Senators who don't vote do count against the vote threshold. So use the total in
        # that case and include present/not voting in the % breakdown.
        if self.required == "3/5" and "Cloture" in self.question: # best way to detect but perhaps imperfect
            total_count_voting = 0 # fall back to total body
        else:
            total_count_voting = len([x for x in all_voters if x.option.key not in ("0", "P")])

        # Find all parties which participated in vote
        # and sort them in order which they should be displayed

        def cmp_party(x):
            """
            Sort the parties by the number of voters in that party.
            """
            return -len([v for v in all_voters if v.party == x])
        
        all_parties = list(set(x.party for x in all_voters))
        all_parties.sort(key=cmp_party)
        total_party_stats = dict((x, {'yes': 0, 'no': 0, 'other': 0, 'total': 0})\
                                 for x in all_parties)

        # Perform a statistical analysis using additional features.
        feature_analysis = self.feature_analysis(all_voters) if include_features else None

        # For each option find the count, the percent of voting members, and the party break down.
        details = []
        for option in all_options:
            voters = voters_by_option.get(option, [])
            if option.key in ("0", "P") and total_count_voting > 0:
                # Present and not-voting are not counted toward passage so they
                # are omitted from the percent, unless this is a quorum call and
                # the only options are present or not voting, in which case we
                # compute percentages across all legislators below.
                percent = None
            else:
                # If this is a yes-no vote, then compute the percentage for this
                # option using the yes/no voters only in the denominator. If there
                # are none (it's a quorum call or Election of the Speaker vote),
                # then compute across the whole body. This gives slightly the wrong
                # idea for cloture votes, which require 3/5ths of senators sworn, i.e.
                # not senators voting but all senators serving.
                percent = int(round(len(voters) / float(total_count_voting or total_count) * 100.0))
            party_stats = dict((x, 0) for x in all_parties)
            for voter in voters:
                party = voter.party
                party_stats[party] += 1
                total_party_stats[party]['total'] += 1
                if option.key == '+':
                    total_party_stats[party]['yes'] += 1
                elif option.key == '-':
                    total_party_stats[party]['no'] += 1
                else:
                    total_party_stats[party]['other'] += 1
            party_counts = [party_stats.get(x, 0) for x in all_parties]
            party_counts = [{"party": all_parties[i], "count": c} for i, c in enumerate(party_counts)]
                
            detail = {'option': option, 'count': len(voters),
                'percent': percent, 'party_counts': party_counts,
                'feature_counts': [{
                  'feature': feature,
                  'count': len([v for v in voters
                                if feature in feature_analysis["featuremap"].get(v.person.id, [])]),
                  'by_party':
                     [ {"party": party,
                        "count": len([v for v in voters if v.party == party
                                     and feature in feature_analysis["featuremap"].get(v.person.id, [])]) }
                        for party in all_parties ]
                   }
                   for feature in feature_analysis["featurelist"]
                 ] if feature_analysis and option.key in ("+", "-") else None
                }
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
        details.sort(key = lambda d : (option_sort_order.get(d['option'].key, 0), -d['count']))
        
        # hide Present/Not Voting if no one voted that way
        details = [d for d in details if d["count"] > 0 or "hide_if_empty" not in d]

        totals = {'options': details, 'max_option_count': max(detail['count'] for detail in details),
                'party_counts': party_counts, 'parties': all_parties,
                'total_count': total_count, 'party_is_caucus': party_is_caucus,
                'features': feature_analysis["featurelist"] if feature_analysis else None
                }
        self._cached_totals = totals
        return totals

    def feature_analysis(self, all_voters):
        # Do a regression analysis using other factors and add all statistically
        # significant factors as additional columns in the output table.

        # Load All Caucus Membership Data
        from person.models import Person
        caucus_membership = Person.load_caucus_membership_data()
        all_caucuses = set(x[0] for x in caucus_membership)

        # Build feature table and vote result vector.
        X = [ ]
        Y = [ ]
        featuremap = { }
        for voter in all_voters:
          if voter.person_role is None: continue # Vice President tie-breaker or missing data
          if voter.option.key not in ("+", "-"): continue # only take yes/no votes
          Y.append(voter.option.key == "+") # make binary
          features = dict([
                   ("intercept", 1), # required
                   ("party", voter.party == "Republican"), # arbitrary
                   ]
                   # Census regions are interesting but are difficult
                   # to explain on the page if we have to say caucus
                   # & regions.
                   # + [
                   #  (region, voter.person_role.state in statelist)
                   #  for region, statelist in census_regions.items()
                   # ]
                   + [
                    (caucus, (caucus, voter.person.bioguideid) in caucus_membership)
                    for caucus in all_caucuses
                   ]
                   )
          X.append(features)
          featuremap[voter.person.id] = set(f for f, v in features.items() if bool(v))
        if len(X) == 0:
          return None

        # Analyze
        from vote.analysis import logistic_regression_fit_best_model
        model = logistic_regression_fit_best_model(X, Y)
        if not model:
          return None

        # When the analysis totally fails we just get all of the features back.
        if len(model["features"]) > 5:
          return None

        # Discard if no features other than the intercept and party are
        # statistically significant. Since party is displayed separately,
        # we don't need to re-include it as a feature. Also limit the
        # total number of features displayed.
        selected_features = list(set(model["features"].keys()) - { "intercept", "party" })[0:5]
        if len(selected_features) == 0:
          return None

        # Put selected_features in order of its coefficient from most positive
        # (aye/yea, which is always listed first on vote pages) to most negative
        # (no/nay).
        selected_features.sort(key = lambda feature : -model["features"][feature]["value"])

        # Simplify the featuremap to only include selected features and put
        # them in the same order as in selected_features.
        featuremap = {
          personid: [f for f in selected_features if f in features]
          for personid, features in featuremap.items()
        }

        # Return a list of features from most to least significant and a map
        # from voters to features.
        return {
          "featurelist": selected_features,
          "featuremap": featuremap
        }

    def summary(self):
        ret = self.result
        if self.total_plus + self.total_minus > 0: # not all votes have aye/no outcomes
	        ret += " " + str(self.total_plus) + "/" + str(self.total_minus)
        else: # in other such cases, like election of the speaker, the winning outcome is not a past tense verb (as in passed)
            ret = "Result: " + ret
        return ret
        
    def get_summary(self):
        try:
            return self.oursummary
        except VoteSummary.DoesNotExist:
            if self.is_on_passage and self.related_bill:
                try:
                   return self.related_bill.oursummary
                except BillSummary.DoesNotExist:
                    pass
        return None

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
            my_reps = sorted(my_reps, key = lambda p : p.sortname_strxfrm)
        else:
            my_reps = []

        # fetch the whole vote and our summary, and keep it cached with this object
        # because in email updates this object is held in memory for the duration of
        # sending out all email updates
        if not hasattr(self, "_cached_event_data"):
            oursummary = self.get_summary()
            all_votes = {
                vv.person: vv.option
                for vv in
                self.voters.select_related('person', 'option')
            }
            self._cached_event_data = [oursummary, all_votes]
        else:
            oursummary, all_votes = self._cached_event_data
        
        return {
            "type": "Vote",
            "date": self.created,
            "title": self.question,
            "url": self.get_absolute_url(),
            "body_text_template":
"""{{summary|safe}}
{% for voter in voters %}{{voter.name|safe}}: {{voter.vote|safe}}
{% endfor %}
{% if oursummary %}{{oursummary.plain_text|truncatewords:120|safe}}{% endif %}""",
            "body_html_template":
"""<p>{{summary}}</p>
{% for voter in voters %}
    <p><a href="{{SITE_ROOT}}{{voter.url}}">{{voter.name}}</a>: {{voter.vote}}</p>
{% endfor %}
{% if oursummary %}{{oursummary.as_html|truncatewords_html:120|safe}}{% endif %}
""",
            "context": {
                "summary": self.summary(),
                "oursummary": oursummary,
                "voters":
                            [
                                { "url": p.get_absolute_url(), "name": p.name_lastonly(), "vote": all_votes[p].value }
                                for p in my_reps if p in all_votes
                            ]
                        if feeds != None else []
                },
            "thumbnail_url": self.get_thumbnail_url(),
            "large_thumbnail_url": self.get_absolute_url() + "/card",
            }
            
    def possible_reconsideration_votes(self, voters=None):
        # Identify possible voters who voted against their view in order to be on the winning
        # side so they may make a motion to reconsider later. Senate only. Since we don't
        # know which option represents the winning option, we just look at party leaders who
        # voted against their party.
        if self.chamber != CongressChamber.senate: return []

        # Get vote totals by party.
        if voters == None:
            voters = self.get_voters()
        by_party = { }
        for voter in voters:
            if not voter.person or not voter.person_role: continue
            if voter.option.key not in ("+", "-"): continue
            by_party.setdefault(voter.person_role.party, {}).setdefault(voter.option_id, set()).add(voter)

        # Find the plurality option by party.
        for party in by_party:
            by_party[party] = max(by_party[party], key = lambda x : len(by_party[party][x]))
    
        # See if any party leaders voted against their party.
        candidates = []
        for voter in voters:
            if voter.person and voter.person_role and voter.person_role.leadership_title:
                if voter.option.key in ("+", "-") and voter.option_id != by_party[voter.person_role.party]:
                    candidates.append(voter)
        return candidates

    def get_thumbnail_url(self):
        return self.get_absolute_url() + "/thumbnail"

    def get_equivalent_aye_voters_us_population_percent(self):
        # Only applicable for senate votes since we are summing state populations.
        if self.chamber != CongressChamber.senate: return None

        # Get the votes as a list of pairs holding (state, "+" | "-" | ...).
        votes = self.voters\
                      .filter(voter_type=VoterType.member)\
                      .exclude(option__key='0')\
                      .values_list('person_role__state', 'option__key')

        # Count up the number of times each state appears in a +/- vote (zero, once, or twice)
        # for the purposes of apportioning states whose votes are split, and the states that
        # have senators at the time of the vote by which senators are listed as serving/eligible
        # to vote.
        state_freq_ayeno = { }
        states_with_voters = set()
        for state, vote in votes:
            if state == "": continue # VP tie-breaker
            states_with_voters.add(state)
            if vote in ("+", "-", "P"): state_freq_ayeno[state] = state_freq_ayeno.get(state, 0) + 1

        # Sum the populations of the states with senators (i.e. the country's population minus DC and territories).
        state_population = get_state_population_in_year(self.created.year)
        total = 0
        for state in states_with_voters:
            if state not in state_population: return None # no population data for a state in this year?
            total += state_population[state]
        if total == 0:
            return None

        # Get the option key that had the most votes, prefering + over - if a tie.
        vote_totals = { }
        for state, vote in votes:
            vote_totals[vote] = vote_totals.get(vote, 0) + 1
        winner_option_key = sorted(vote_totals.items(), key = lambda kv : (-kv[1], kv[0]))[0][0]

        # Sum the apportioned state populations of the winning votes (i.e. if senators split,
        # apportion half their state's population to each; if a senator doesn't vote, apportion
        # the whole population to the voting senator).
        winner = 0
        for state, vote in votes:
            if vote == winner_option_key and state in state_population:
               winner += state_population[state] / state_freq_ayeno[state]

        # Return the proportion of winner votes as well as which option we considered the winner.
        return (winner_option_key, winner/total*100)

    @staticmethod
    def analyze_equivalent_aye_voters_us_population_percent():
        import tqdm
        for vote in tqdm.tqdm(list(Vote.objects\
            .filter(
                    total_plus__gt=0, # votes without ayes are not relevant
                    chamber=CongressChamber.senate, # in the senate
                    congress__gte=57, # first Congress than began after 1900 when we first have pop data
                    category__in=Vote.MAJOR_CATEGORIES, # there are crazy-low population percents for some procedural votes
            )\
            .order_by('-created'))):
            print(vote.created.year, vote.get_absolute_url(), vote.category, *vote.get_equivalent_aye_voters_us_population_percent(), sep=",")

class VoteOption(models.Model):
    vote = models.ForeignKey('vote.Vote', related_name='options', on_delete=models.CASCADE)
    key = models.CharField(max_length=20)
    value = models.CharField(max_length=255)
    winner = models.BooleanField(null=True, help_text="If known, whether this Option is the one that was the vote's winner.")

    def __repr__(self):
        return "<{} {}>".format(self.key, self.value)
        
    def __str__(self):
        return self.value
        
    @property
    def alpha_key(self):
        if self.key == "+": return "positive"
        if self.key == "-": return "negative"
        if self.key == "0": return "absent"
        if self.key == "present": return "present"
        return "other"

    @property
    def norm_text(self):
        if self.key == "+": return "Yes"
        if self.key == "-": return "No"
        return str(self)

class Voter(models.Model):
    """How people voted on roll call votes in the U.S. Congress since 1789. See the Vote API. Filter on the vote field to get the results of a particular vote."""
	
    vote = models.ForeignKey('vote.Vote', related_name='voters', on_delete=models.PROTECT, help_text="The vote that this record is a part of.")
    person = models.ForeignKey('person.Person', blank=True, null=True, on_delete=models.PROTECT, related_name='votes', help_text="The person who cast this vote. May be null if the information could not be determined.")
    person_role = models.ForeignKey('person.PersonRole', blank=True, null=True, on_delete=models.PROTECT, related_name='votes', help_text="The role of the person who cast this vote at the time of the vote. May be null if the information could not be determined.")
    voter_type = models.IntegerField(choices=VoterType, help_text="Whether the voter was a Member of Congress or the Vice President.")
    option = models.ForeignKey('vote.VoteOption', on_delete=models.CASCADE, help_text="How the person voted.")
    voteview_extra_code = models.CharField(max_length=20, help_text="Extra information provided in the voteview data.")
    created = models.DateTimeField(db_index=True, help_text="The date (and in recent history also time) on which the vote was held.") # equal to vote.created
    
    api_recurse_on = ('vote', 'person', 'person_role', 'option')
    api_example_parameters = { "sort": "-created" }
    api_filter_if = { "option__key": ["person"] }
    
    def __str__(self):
        return '%s /%s/ %s' % (str(self.person), self.option.key, str(self.vote))
        
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

    @staticmethod
    def get_role_for(person, vote, vote_date):
        # TODO filter chamber in case person went between chambers same day?
        role = person.get_role_at_date(vote_date, congress=vote.congress)
        if role is not None: return role

        # Find closest.
        for role in person.roles.all():
            if role.congress_numbers() is not None and vote.congress in role.congress_numbers():
                return role

        return None

    def is_valid(self):
        return self.person_role.startdate <= self.created.date() <= self.person_role.enddate and (self.person_role.congress_numbers() is None or self.vote.congress in self.person_role.congress_numbers())

    @staticmethod
    def fixup_roles():
        # Sometimes the role column becomes incorrect if the PersonRole instance is updated
        # to new dates.

        # Fetch Voter objects in chunks since we can't call .all() on the whole table.
        # Get all of the IDs first, then chunk the IDs, and fetch objects for each chunk.
        def fetch_in_chunks(qs, chunk_size):
            all_items = qs.values_list("id", flat=True)
            def make_iter(all_items):
                while all_items:
                    chunk = all_items[0:chunk_size]
                    all_items = all_items[len(chunk):]
                    for c in qs.in_bulk(chunk).values():
                        yield c
            return len(all_items), make_iter(list(all_items))

        # Iterate over all of the records. Check validity. Update where needed.
        import tqdm
        total, voters = fetch_in_chunks(
           Voter.objects
             # filter for likely problem cases - there are too many Voter objects to process them all in a reasonable amount of time
             .filter(Q(created__lte=F('person_role__startdate')) | Q(created__gte=F('person_role__enddate')) | Q(person_role=None))
             .order_by('created', 'person_id', 'vote_id')
             .select_related("person", "person_role", "vote"),
             2500)
        for v in tqdm.tqdm(voters, total=total):
            if not v.person_role or not v.is_valid():
                new_role = Voter.get_role_for(v.person, v.vote, v.created)
                if new_role != v.person_role:
                    print(v.person, v.created, v.vote)
                    print(v.person_role, "=>", new_role)
                    print()
                    v.person_role = new_role
                    v.save()


# Summaries
class VoteSummary(models.Model):
    vote = models.OneToOneField(Vote, related_name="oursummary", on_delete=models.PROTECT)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    content = models.TextField(blank=True)

    def __str__(self): return "Summary for " + str(self.vote)
    def get_absolute_url(self): return self.vote.get_absolute_url()

    def as_html(self):
        return markdown(self.content)

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

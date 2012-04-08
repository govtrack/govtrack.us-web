# -*- coding: utf-8 -*-
from django.db import models
from django.template.defaultfilters import slugify
from django.conf import settings
from django.core.cache import cache

import datetime
from dateutil.relativedelta import relativedelta

from common import enum
from person.types import Gender, RoleType, SenatorClass, State
from name import get_person_name

from us import stateapportionment, get_congress_dates, statenames, get_session_from_date

import functools
def cache_result(f):
    @functools.wraps(f)
    def g(self):
        if hasattr(self, "role"): return f(self)
        ckey = "cache_result_%s_%s_%d" % (self.__class__.__name__, f.__name__, self.id)
        v = cache.get(ckey)
        if not v:
            v = f(self)
            cache.set(ckey, v)
        return v
    return g

class Person(models.Model):
    firstname = models.CharField(max_length=255)
    lastname = models.CharField(max_length=255)
    middlename = models.CharField(max_length=255, blank=True)

    # misc
    birthday = models.DateField(blank=True, null=True)
    gender = models.IntegerField(choices=Gender, blank=True, null=True)
    
    # namemod set(['II', 'Jr.', 'Sr.', 'III', 'IV'])
    namemod = models.CharField(max_length=10, blank=True)
    nickname = models.CharField(max_length=255, blank=True)

    # links
    bioguideid = models.CharField(max_length=255, blank=True, null=True) #  bioguide.congress.gov (null for presidents that didn't serve in Congress)
    pvsid = models.CharField(max_length=255, blank=True) #  vote-smart.org
    osid = models.CharField(max_length=255, blank=True) #  opensecrets.org
    metavidid = models.CharField(max_length=255, blank=True) # metavid.org
    youtubeid = models.CharField(max_length=255, blank=True) # YouTube
    twitterid = models.CharField(max_length=50, blank=True) # Twitter

    # indexing
    def get_index_text(self):
        return self.name_no_details()
    haystack_index = ('lastname', 'gender')
    haystack_index_extra = (('most_recent_role_type', 'Char'), ('is_currently_serving', 'Boolean'), ('most_recent_role_state', 'Char'), ('most_recent_role_district', 'Integer'), ('most_recent_role_party', 'Char'))
    #######

    def __unicode__(self):
        return self.name

    @property
    def fullname(self):
        return u'%s %s' % (self.firstname, self.lastname)

    @property
    @cache_result
    def name(self):
           return get_person_name(self, firstname_position='before', role_recent=True)

    @cache_result
    def name_no_district(self):
        return get_person_name(self, firstname_position='before', role_recent=True, show_district=False)

    @cache_result
    def name_no_details(self):
        return get_person_name(self, firstname_position='before')
        
    @cache_result
    def name_no_details_lastfirst(self):
        return get_person_name(self, firstname_position='after')
            
    @cache_result
    def name_and_title(self):
        return get_person_name(self, firstname_position='before', role_recent=True, show_party=False, show_district=False)
       
    @property
    @cache_result
    def sortname(self):
        return get_person_name(self, firstname_position='after', role_recent=True, show_district=True, show_title=False, show_type=True)
        
    def get_current_role(self):
        try:
            return self.roles.get(current=True)
        except PersonRole.DoesNotExist:
            return None
    def is_currently_serving(self):
        return self.roles.filter(current=True).exists()

    def get_absolute_url(self):
        name = slugify('%s %s' % (self.firstname, self.lastname))
        name = name.replace('-', '_')
        return '/congress/members/%s/%d' % (name, self.pk)

    def get_age(self):
        if not self.birthday:
            return 0
        else:
            today = datetime.date.today()
            return relativedelta(today, self.birthday).years

    def roles_condensed(self):
        ret = []
        for role in self.roles.order_by('startdate'):
            if len(ret) > 0 and role.continues_from(ret[-1]):
                ret[-1].id = None # prevent corruption
                ret[-1].enddate = role.enddate
            else:
                ret.append(role)
        ret.reverse()
        return ret

    def get_role_at_date(self, when):
        if isinstance(when, datetime.datetime):
            when = when.date()
        
        # A person may have two roles on the same date, such as when simultaneously
        # resigning from the House to take office in the Senate. In that case, return the
        # most recent role.
        try:
            return self.roles.filter(startdate__lte=when, enddate__gte=when).order_by("-startdate")[0]
        except IndexError:
            return None

    def get_last_role_at_congress(self, congress):
        start, end = get_congress_dates(congress)
        try:
            return self.roles.filter(startdate__lte=end, enddate__gte=start).order_by('-startdate')[0]
        except IndexError:
            return None
            
    def get_role_at_year(self, year):
        try:
            return self.roles.filter(startdate__lte=("%d-12-31"%year), enddate__gte=("%d-01-01"%year)).order_by('-startdate')[0]
        except IndexError:
            return None
            
    def get_most_recent_role(self):
        try:
            return self.roles.order_by('-startdate')[0]
        except IndexError:
            return None

    def get_most_recent_role_field(self, fieldname):
        role = self.get_most_recent_role()
        if not role: return None
        ret = getattr(role, fieldname)
        if callable(ret): ret = ret()
        return ret
    def most_recent_role_type(self):
        return self.get_most_recent_role_field('get_title')
    def most_recent_role_state(self):
        return self.get_most_recent_role_field('state')
    def most_recent_role_district(self):
        return self.get_most_recent_role_field('district')
    def most_recent_role_party(self):
        return self.get_most_recent_role_field('party')
    def most_recent_role_congress(self):
        return self.get_most_recent_role_field('most_recent_congress_number')

    def get_photo_url(self):
        """
        Return URL of 100px photo.
        """

        return '/data/photos/%d-100px.jpeg' % self.pk

    class Meta:
        ordering = ['lastname', 'firstname']

    def vote_sources(self):
        from vote.models import Vote
        sources = set()
        for v in Vote.objects.filter(voters__person=self).values("source").distinct():
            if v["source"] in (1, 2):
                sources.add("congress")
            elif v["source"] == 3:
                sources.add("keithpoole")
        return sources

class PersonRole(models.Model):
    person = models.ForeignKey('person.Person', related_name='roles')
    role_type = models.IntegerField(choices=RoleType)
    current = models.BooleanField(default=False, choices=[(False, "No"), (True, "Yes")])
    startdate = models.DateField(db_index=True)
    enddate = models.DateField(db_index=True)
    # http://en.wikipedia.org/wiki/Classes_of_United_States_Senators
    senator_class = models.IntegerField(choices=SenatorClass, blank=True, null=True) # None for representatives
    # http://en.wikipedia.org/wiki/List_of_United_States_congressional_districts
    district = models.IntegerField(blank=True, null=True) # None for senators/presidents
    state = models.CharField(choices=sorted(State, key = lambda x : x[0]), max_length=2, blank=True)
    party = models.CharField(max_length=255, blank=True, null=True)
    website = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['startdate']

    def __unicode__(self):
        return '%s / %s to %s / %s' % (self.person.fullname, self.startdate, self.enddate, self.get_role_type_display())
       
    def continues_from(self, prev):
        if self.startdate - prev.enddate > datetime.timedelta(days=120): return False
        if self.role_type != prev.role_type: return False
        if self.senator_class != prev.senator_class: return False
        if self.state != prev.state: return False
        if self.district != prev.district: return False
        return True

    def get_title(self):
        return self.get_title_name(short=False)

    def get_title_abbreviated(self):
        return self.get_title_name(short=True)

    def get_title_name(self, short):
        if self.role_type == RoleType.president:
            return 'President'
        if self.role_type == RoleType.senator:
            return 'Sen.' if short else 'Senator'
        if self.role_type == RoleType.representative:
            if not self.state in stateapportionment:
                return 'Del.' if short else 'Delegate'
            if self.state == 'PR':
                return 'Res.Com.' if short else 'Resident Commissioner'
            if stateapportionment[self.state] == 'T':
                return 'Del.' if short else 'Delegate'
            return 'Rep.' if short else 'Representative'
            
    def state_name(self):
        return State.by_value(self.state).label
            
    def get_description(self):
        from django.contrib.humanize.templatetags.humanize import ordinal
        
        if self.role_type == RoleType.president:
            return self.get_title_name(False)
        if self.role_type == RoleType.senator:
            return self.get_title_name(False) + " from " + statenames[self.state]
        if self.role_type == RoleType.representative:
            if self.district == -1:
                return self.get_title_name(False) + " for " + statenames[self.state]
            elif self.district == 0:
                return self.get_title_name(False) + " for " + statenames[self.state] + " At Large"
            else:
                return self.get_title_name(False) + " for " + statenames[self.state] + "'s " + ordinal(self.district) + " congressional district"

    def congress_numbers(self):
        # Senators can span Congresses, so return a range.
        cs1 = get_session_from_date(self.startdate)
        cs2 = get_session_from_date(self.enddate)
        if not cs1: return None
        if not cs2: cs2 = (settings.CURRENT_CONGRESS, None)
        return range(cs1[0], cs2[0]+1) # congress number only, not session
    def most_recent_congress_number(self):
        n = self.congress_numbers()
        if not n: return None
        return n[-1]

    def create_events(self, prev_role, next_role):
        now = datetime.datetime.now().date()
        from events.models import Feed, Event
        with Event.update(self) as E:
            f = Feed.PersonFeed(self.person_id)
            if not prev_role or not self.continues_from(prev_role):
                E.add("termstart", self.startdate, f)
            if not next_role or not next_role.continues_from(self):
                if self.enddate <= now: # because we're not sure of end date until it happens
                    E.add("termend", self.enddate, f)
        
    def render_event(self, eventid, feeds):
        self.person.role = self # affects name generation
        return {
            "type": "Elections and Offices",
            "date_has_no_time": True,
            "date": self.startdate if eventid == "termstart" else self.enddate,
            "title": self.person.name + (" takes office as " if eventid == "termstart" else " leaves office as ") + self.get_description(),
            "url": self.person.get_absolute_url(),
            "body_text_template": "",
            "body_html_template": "",
            "context": {}
            }

    def logical_dates(self):
        startdate = None
        enddate = None
        prev_role = None
        found_me = False
        for role in self.person.roles.filter(role_type=self.role_type, senator_class=self.senator_class, state=self.state, district=self.district).order_by('startdate'):
            if found_me and not role.continues_from(prev_role):
                break
            if prev_role == None or not role.continues_from(prev_role):
                startdate = role.startdate
            enddate = role.enddate
            prev_role = role
            if role.id == self.id:
                found_me = True
        return (startdate, enddate)


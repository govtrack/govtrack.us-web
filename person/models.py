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
    firstname = models.CharField(max_length=255, help_text="The person's first name or first initial.")
    lastname = models.CharField(max_length=255, help_text="The person's last name.")
    middlename = models.CharField(max_length=255, blank=True, help_text="The person's middle name (optional).")

    # misc
    birthday = models.DateField(blank=True, null=True, help_text="The person's birthday.")
    gender = models.IntegerField(choices=Gender, blank=True, null=True, help_text="The person's gender, if known. For historical data, the gender is sometimes not known.")
    
    # namemod set(['II', 'Jr.', 'Sr.', 'III', 'IV'])
    namemod = models.CharField(max_length=10, blank=True, help_text="The suffix on the person's name usually one of Jr., Sr., I, II, etc.")
    nickname = models.CharField(max_length=255, blank=True, help_text="The person's nickname. If set, the nickname should usually be displayed in quotes where a middle name would go. For instance, Joe \"Buster\" Smith.")

    # links
    bioguideid = models.CharField(max_length=255, blank=True, null=True, help_text="The person's ID on bioguide.congress.gov. May be null if the person served only as a president and not in Congress.")
    pvsid = models.CharField(max_length=255, blank=True, help_text="The person's ID on vote-smart.org (Project Vote Smart), if known.")
    osid = models.CharField(max_length=255, blank=True, help_text="The person's ID on opensecrets.org (The Center for Responsive Politics), if known.")
    metavidid = models.CharField(max_length=255, blank=True, help_text="The person's ID on metavid.org, if known.")
    youtubeid = models.CharField(max_length=255, blank=True, help_text="The name of the person's official YouTube channel, if known.")
    twitterid = models.CharField(max_length=50, blank=True, help_text="The name of the person's official Twitter handle, if known.")

    # indexing
    def get_index_text(self):
        return self.name_no_details()
    haystack_index = ('lastname', 'gender')
    haystack_index_extra = (('most_recent_role_type', 'Char'), ('is_currently_serving', 'Boolean'), ('most_recent_role_state', 'Char'), ('most_recent_role_district', 'Integer'), ('most_recent_role_party', 'Char'), ('was_moc', 'Boolean'), ('is_currently_moc', 'Boolean'))
    #######

    def __unicode__(self):
        return self.name

    @property
    def fullname(self):
        return u'%s %s' % (self.firstname, self.lastname)

    @property
    @cache_result
    def name(self):
    	"""The person's full name with title, district, and party information for current Members of Congress."""
        return get_person_name(self, firstname_position='before', role_recent=True)

    @cache_result
    def name_no_district(self):
        return get_person_name(self, firstname_position='before', role_recent=True, show_district=False)

    @cache_result
    def name_no_details(self):
    	"""The person's full name (excluding all title details)."""
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
    	"""The person's name suitable for sorting lexicographically by last name or for display in a sorted list of names. Title, district, and party information are included for current Members of Congress."""
        return get_person_name(self, firstname_position='after', role_recent=True, show_district=True, show_title=False, show_type=True)
        
    @property
    def current_role(self):
        return self.get_current_role()
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

    def get_most_recent_role_field(self, fieldname, current=False):
        if not current:
            role = self.get_most_recent_role()
        else:
            role = self.get_current_role()
        if not role: return None
        ret = getattr(role, fieldname)
        if callable(ret): ret = ret()
        return ret
    def most_recent_role_typeid(self, current=False):
        return self.get_most_recent_role_field('role_type', current=current)
    def most_recent_role_type(self, current=False):
        return self.get_most_recent_role_field('get_title', current=current)
    def most_recent_role_state(self, current=False):
        return self.get_most_recent_role_field('state', current=current)
    def most_recent_role_district(self, current=False):
        return self.get_most_recent_role_field('district', current=current)
    def most_recent_role_party(self, current=False):
        return self.get_most_recent_role_field('party', current=current)
    def most_recent_role_congress(self):
        return self.get_most_recent_role_field('most_recent_congress_number')
    def was_moc(self):
        return self.roles.filter(role_type__in=(RoleType.representative, RoleType.senator)).exists() # ability to exclude people who only were president
    def is_currently_moc(self):
        return self.roles.filter(current=True, role_type__in=(RoleType.representative, RoleType.senator)).exists()

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
    role_type = models.IntegerField(choices=RoleType, help_text="The type of this role: a U.S. senator, a U.S. congressperson, or a U.S. president.")
    current = models.BooleanField(default=False, choices=[(False, "No"), (True, "Yes")], help_text="Whether the role is currently held, or if this is archival information.")
    startdate = models.DateField(db_index=True, help_text="The date the role began (when the person took office).")
    enddate = models.DateField(db_index=True, help_text="The date the role ended (when the person resigned, died, etc.)")
    # http://en.wikipedia.org/wiki/Classes_of_United_States_Senators
    senator_class = models.IntegerField(choices=SenatorClass, blank=True, null=True, help_text="For senators, their election class, which determines which years they are up for election. (It has nothing to do with seniority.)") # None for representatives
    # http://en.wikipedia.org/wiki/List_of_United_States_congressional_districts
    district = models.IntegerField(blank=True, null=True, help_text="For representatives, the number of their congressional district. 0 for at-large districts, -1 in historical data if the district is not known.") # None for senators/presidents
    state = models.CharField(choices=sorted(State, key = lambda x : x[0]), max_length=2, blank=True, help_text="For senators and representatives, the two-letter USPS abbrevation for the state or territory they are serving. Values are the abbreviations for the 50 states (each of which have at least one representative and two senators, assuming no vacancies) plus DC, PR, and the island territories AS, GU, MP, and VI (all of which have a non-voting delegate), and for really old historical data you will also find PI (Philippines, 1907-1946), DK (Dakota Territory, 1861-1889), and OR (Orleans Territory, 1806-1811) for non-voting delegates.")
    party = models.CharField(max_length=255, blank=True, null=True, help_text="The political party of the person. If the person changes party, it is usually the most recent party during this role.")
    website = models.CharField(max_length=255, blank=True, help_text="The URL to the official website of the person during this role, if known.")

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
    	"""The long form of the title used to prefix the names of people with this role: Representative, Senator, President, Delegate, or Resident Commissioner."""
        return self.get_title_name(short=False)

    def get_title_abbreviated(self):
    	"""The title used to prefix the names of people with this role: Rep., Sen., President, Del. (delegate), or Res.Com. (resident commissioner)."""
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
    	"""A description of this role, e.g. Delegate for District of Columbia At Large."""
    	
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
    	"""The Congressional sessions (Congress numbers) that this role spans, as a list from the starting Congress number through consecutive numbers to the ending Congress number."""
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


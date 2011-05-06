# -*- coding: utf-8 -*-
from django.db import models
from django.template.defaultfilters import slugify
import datetime
from dateutil.relativedelta import relativedelta

from common import enum
from person.types import Gender, RoleType, SenatorClass, State
from name import get_person_name

from us import stateapportionment, get_congress_dates, statenames

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

    # Cached roles, see `get_role_at_date` docstring
    _cached_roles = set()

    @property
    def fullname(self):
        return u'%s %s' % (self.firstname, self.lastname)

    @property
    def name(self):
        return get_person_name(self, firstname_position='before')

    def name_no_district(self):
        return get_person_name(self, firstname_position='before', show_district=False)

    def name_no_details(self):
        return get_person_name(self, firstname_position='before', show_district=False, show_party=False)
        
    def name_no_details_lastfirst(self):
        return get_person_name(self, firstname_position='after', show_district=False, show_party=False)
			
    def __unicode__(self):
        return self.name

    def get_current_role(self):
        try:
            return self.roles.get(current=True)
        except PersonRole.DoesNotExist:
            return None

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
        for role in self._cached_roles:
            if role.startdate <= when <= role.enddate:
                return role
        try:
            role = self.roles.get(startdate__lte=when, enddate__gte=when)
            self._cached_roles.add(role)
            return role
        except PersonRole.DoesNotExist:
            return None

    def get_last_role_at_congress(self, congress):
        start, end = get_congress_dates(congress)
        try:
            return self.roles.filter(startdate__lte=end, enddate__gte=start).order_by('-startdate')[0]
        except IndexError:
            return None

    def get_photo_url(self):
        """
        Return URL of 100px photo.
        """

        return '/data/photos/%d-100px.jpeg' % self.pk

    def cache_role(self, role):
        """
        Save role to cache.
        """

        self._cached_roles.add(role)

    class Meta:
        ordering = ['lastname', 'firstname']


class PersonRole(models.Model):
    person = models.ForeignKey('person.Person', related_name='roles')
    role_type = models.IntegerField(choices=RoleType)
    current = models.BooleanField(blank=True, default=False, choices=[(False, "No"), (True, "Yes")])
    startdate = models.DateField(db_index=True)
    enddate = models.DateField(db_index=True)
    # http://en.wikipedia.org/wiki/Classes_of_United_States_Senators
    senator_class = models.IntegerField(choices=SenatorClass, blank=True, null=True)
    # http://en.wikipedia.org/wiki/List_of_United_States_congressional_districts
    district = models.IntegerField(blank=True, null=True) 
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
            
    def get_description(self):
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
                return self.get_title_name(False) + " for " + statenames[self.state] + "'s District " + str(self.district)

    def create_events(self):
        now = datetime.datetime.now().date()
        if self.enddate < now-datetime.timedelta(days=365*2):
            return
        from events.feeds import PersonFeed
        from events.models import Event
        with Event.update(self) as E:
            E.add("termstart", self.startdate, PersonFeed(self.person_id))
            if self.enddate <= now: # because we're not sure of end date until it happens
                E.add("termend", self.enddate, PersonFeed(self.person_id))
	
    def render_event(self, eventid, feeds):
        import events.feeds
        return {
            "type": "Elections",
            "date_has_no_time": True,
            "date": self.startdate if eventid == "termstart" else self.enddate,
            "title": self.person.name + (" takes office as " if eventid == "termstart" else " leaves office as ") + self.get_description(),
            "url": self.person.get_absolute_url(),
            "body_text_template": "",
            "body_html_template": "",
            "context": {}
            }


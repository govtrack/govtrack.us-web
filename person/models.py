# -*- coding: utf-8 -*-
from django.db import models
from django.template.defaultfilters import slugify
import datetime
from dateutil.relativedelta import relativedelta

from common import enum
from person.types import Gender, RoleType, SenatorClass, State
from name import get_person_name

class Person(models.Model):
    firstname = models.CharField(max_length=255)
    lastname = models.CharField(max_length=255)
    middlename = models.CharField(max_length=255, blank=True)

    #  bioguide.congress.gov
    bioguidedid = models.CharField(max_length=255) #  bioguide.congress.gov
    pvsid = models.CharField(max_length=255, blank=True) #  bioguide.congress.gov
    osid = models.CharField(max_length=255, blank=True) #  bioguide.congress.gov

    # Misc
    birthday = models.DateField(blank=True, null=True)
    gender = models.IntegerField(choices=Gender, blank=True, null=True)
    metavidid = models.CharField(max_length=255, blank=True)
    youtubeid = models.CharField(max_length=255, blank=True)
    # religion set(['Catholic', 'Episcopalian', 'Unknown', 'Non-Denominational', 'Reformed Latter Day Saint', 'Unitarian', 'African Methodist Episcopal', 'Lutheran', 'Seventh Day Adventist', 'Christian', 'Latter Day Saints', 'Assembly of God', 'Church of Christ', 'Jewish', 'Moravian', 'Seventh-Day Adventist', 'Roman Catholic', 'Unitarian Universalist', 'Protestant', 'United Church of Christ', 'Presbyterian', 'Nazarene', 'United Methodist', 'Congregationalist', 'Reformed Church in America', 'Zion Lutheran', 'United Brethren in Christ', 'First Christian Church (Disciples of Christ)', 'Methodist', 'Christian Reformed', 'Episcopal', 'Second Baptist', 'Christian Scientist', 'Southern Baptist', 'Baptist', 'Greek Orthodox'])
    religion = models.CharField(max_length=255, blank=True)
    
    # namemod set(['II', 'Jr.', 'Sr.', 'III', 'IV'])
    namemod = models.CharField(max_length=10, blank=True)
    nickname = models.CharField(max_length=255, blank=True)

    @property
    def fullname(self):
        return u'%s %s' % (self.firstname, self.lastname)

    @property
    def name(self):
        return get_person_name(self, firstname_position='before')

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
        return '/person/%s/%d' % (name, self.pk)

    def get_age(self):
        if not self.birthday:
            return 0
        else:
            today = datetime.date.today()
            return relativedelta(today, self.birthday).years

    def get_role_at_date(self, date):
        try:
            return self.roles.get(startdate__lte=date, enddate__gte=date)
        except PersonRole.DoesNotExist:
            return None

    def get_last_role_at_congress(self, congress):
        start, end = get_congress_dates(date_or_congress)
        try:
            return self.roles.filter(startdate__lte=end, enddate__gte=start).order_by('-startdate')[0]
        except IndexError:
            return None


class PersonRole(models.Model):
    person = models.ForeignKey('person.Person', related_name='roles')
    role_type = models.IntegerField(choices=RoleType)
    current = models.BooleanField(blank=True, default=False)
    startdate = models.DateField()
    enddate = models.DateField()
    # http://en.wikipedia.org/wiki/Classes_of_United_States_Senators
    senator_class = models.IntegerField(choices=SenatorClass, blank=True, null=True)
    # http://en.wikipedia.org/wiki/List_of_United_States_congressional_districts
    district = models.IntegerField(blank=True, null=True) 
    state = models.CharField(choices=State, max_length=255, blank=True)
    party = models.CharField(max_length=255)

    class Meta:
        ordering = ['startdate']

    def __unicode__(self):
        return '%s / %s / %s' % (self.person.fullname, self.startdate, self.get_role_type_display())

    def get_title(self):
        return self.get_title_name(short=False)

    def get_title_abbreviated(self):
        return self.get_title_name(short=True)

    def get_title_name(self, short):
        stateapportionment = {'AL': 7, 'AK': 1, 'AS': 'T', 'AZ': 8, 'AR': 4, 'CA': 53, 'CO': 7, 'CT': 5, 'DE': 1, 'DC': 'T', 'FL': 25, 'GA': 13, 'GU': 'T', 'HI': 2, 'ID': 2, 'IL': 19, 'IN': 9, 'IA': 5, 'KS': 4, 'KY': 6, 'LA': 7, 'ME': 2, 'MD': 8, 'MA': 10, 'MI': 15, 'MN': 8, 'MS': 4, 'MO': 9, 'MT': 1, 'NE': 3, 'NV': 3, 'NH': 2, 'NJ': 13, 'NM': 3, 'NY': 29, 'NC': 13, 'ND':  1, 'MP': 'T', 'OH': 18, 'OK': 5, 'OR': 5, 'PA': 19, 'PR': 'T', 'RI': 2, 'SC': 6, 'SD': 1, 'TN': 9, 'TX': 32, 'UT': 3, 'VT': 1, 'VI': 'T', 'VA': 11, 'WA': 9, 'WV': 3, 'WI': 8, 'WY': 1}
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

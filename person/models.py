# -*- coding: utf-8 -*-
from django.db import models

from common import enum

class Gender(enum.Enum):
    male = enum.Item(1, 'Male')
    female = enum.Item(2, 'Female')

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
    
    # Role related
    # title set(['Rep.', 'Res.Comm.', 'Sen.', 'Del.'])
    title = models.CharField(max_length=20, blank=True)# enum?
    # state set(['WA', 'DE', 'DC', 'WI', 'WV', 'HI', 'FL', 'AK', 'NH', 'NJ', 'NM', 'TX', 'LA', 'NC', 'ND', 'NE', 'TN', 'NY', 'PA', 'WY', 'RI', 'NV', 'VA', 'GU', 'CO', 'VI', 'CA', 'AL', 'AS', 'AR', 'VT', 'IL', 'GA', 'IN', 'IA', 'OK', 'AZ', 'ID', 'CT', 'ME', 'MD', 'MA', 'OH', 'UT', 'MO', 'MN', 'MI', 'KS', 'MT', 'MP', 'MS', 'PR', 'SC', 'KY', 'OR', 'SD'])
    state = models.CharField(max_length=2, blank=True) # TODO: convert into enum
    district = models.IntegerField(blank=True, null=True) 
    # namemod set(['II', 'Jr.', 'Sr.', 'III', 'IV'])
    namemod = models.CharField(max_length=10, blank=True)
    nickname = models.CharField(max_length=255, blank=True)

    @property
    def name(self):
        return u'%s %s' % (self.firstname, self.lastname)

    def __unicode__(self):
        return self.name


class RoleType(enum.Enum):
    senator = enum.Item(1, 'Senator')
    congressman = enum.Item(2, 'Congressman')
    president = enum.Item(3, 'President')


class SenatorClass(enum.Enum):
    class1 = enum.Item(1, 'Class 1')
    class2 = enum.Item(2, 'Class 2')
    class3 = enum.Item(3, 'Class 3')


class PersonRole(models.Model):
    person = models.ForeignKey('person.Person')
    role_type = models.IntegerField(choices=RoleType)
    current = models.BooleanField(blank=True, default=False)
    startdate = models.DateField()
    enddate = models.DateField()
    # http://en.wikipedia.org/wiki/Classes_of_United_States_Senators
    senator_class = models.IntegerField(choices=SenatorClass, blank=True, null=True)
    # http://en.wikipedia.org/wiki/List_of_United_States_congressional_districts
    district = models.IntegerField(blank=True, null=True) 
    state = models.CharField(max_length=255, blank=True) # TODO: convert into enum
    party = models.CharField(max_length=255)


"""
class State(enum.Enum):
    For senators and representatives, the state attribute gives the USPS state abbreviation of the state or territory they represent. Besides the 50 states, this includes delegates from American Samoa (AS), District of Columbia (DC), Guam (GU), Northern Mariana Islands (MP), Puerto Rico (PR), Virgin Islands (VI), and the former (for historical data) Dakota Territory (DK), Philippines Territory/Commonwealth (PI), and Territory of Orleans (OL). Puerto Rico's delegate is called a Resident Commissioner.
"""

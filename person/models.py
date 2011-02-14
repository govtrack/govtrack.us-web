# -*- coding: utf-8 -*-
from django.db import models
from django.template.defaultfilters import slugify

from common import enum
from person.types import Gender, RoleType, SenatorClass, State

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
    title = models.CharField(max_length=20, blank=True)# Should it be Enum class?
    state = models.CharField(choices=State, max_length=2, blank=True)
    district = models.IntegerField(blank=True, null=True) 
    # namemod set(['II', 'Jr.', 'Sr.', 'III', 'IV'])
    namemod = models.CharField(max_length=10, blank=True)
    nickname = models.CharField(max_length=255, blank=True)

    @property
    def name(self):
        full_name = u'%s %s' % (self.firstname, self.lastname)
        role = self.get_current_role()
        if not role:
            return full_name
        else:
            head = self.title
            chunk1 = role.party[0].upper()
            if self.state:
                chunk2 = self.state
                if self.district:
                    chunk2 += '-%s' % role.district
            else:
                chunk2 = ''
            chunks = [chunk1, chunk2] if chunk2 else [chunk1]
            tail = '[%s]' % ', '.join(chunks)
            return u'%s %s %s' % (head, full_name, tail)

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



# -*- coding: utf-8 -*-
from django.db import models
from django.template.defaultfilters import slugify
import datetime
from dateutil.relativedelta import relativedelta

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
    def fullname(self):
        return u'%s %s' % (self.firstname, self.lastname)

    @property
    def name(self):
        role = self.get_current_role()
        if not role:
            return self.fullname
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
            return u'%s %s %s' % (head, self.fullname, tail)

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
    website = models.CharField(max_length=255, blank=True, null=True)

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


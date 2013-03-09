# -*- coding: utf-8 -*-
from django.db import models
from django.core.urlresolvers import reverse

from common import enum

class CommitteeType(enum.Enum):
    senate = enum.Item(1, 'Senate', abbrev="S")
    joint = enum.Item(2, 'Joint', abbrev="J")
    house = enum.Item(3, 'House', abbrev="H")


class Committee(models.Model):
    """
    Holds info about committees and subcommittees.

    Subcommittees have only code, name, parent nonblank attributes.
    """

    # committee_type applies to committees but not subcommittees
    committee_type = models.IntegerField(choices=CommitteeType, blank=True, null=True)
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=255)
    url = models.CharField(max_length=255, blank=True, null=True)
    abbrev = models.CharField(max_length=255, blank=True)
    obsolete = models.BooleanField(blank=True, default=False)
    committee = models.ForeignKey('self', blank=True, null=True, related_name='subcommittees', on_delete=models.PROTECT)

    def __unicode__(self):
        return self.name

    class Meta:
        ordering = ['name']

    def get_absolute_url(self):
        parent = self.committee
        if parent:
            return reverse('subcommittee_details', args=[parent.code, self.code])
        else:
            return reverse('committee_details', args=[self.code])
    
    @property
    def fullname(self):
        if self.committee == None:
            return self.name
        else:
            return self.committee.name + ": Subcommittee on " + self.name

    @property
    def shortname(self):
	    return self.fullname.replace("Committee on the ", "").replace("Committee on ", "")

    @property
    def name_no_article(self):
            n = self.name
            if n.startswith("the "): n = n[4:]
            return n

    def committee_type_abbrev(self):
        return CommitteeType.by_value(self.committee_type).abbrev
    
    def create_events(self):
        from events.models import Feed, Event
        with Event.update(self) as E:
            for meeting in self.meetings.all():
                E.add("mtg_" + str(meeting.id), meeting.when, [Feed.AllCommitteesFeed(), Feed.CommitteeFeed(self.code)]
                	+ [Feed.BillFeed(b) for b in meeting.bills.all()])
    
    def render_event(self, eventid, feeds):
        eventinfo = eventid.split("_")
        mtg = CommitteeMeeting.objects.get(id=eventinfo[1])
        
        return {
            "type": "Committee Meeting",
            "date": mtg.when,
            "title": self.fullname + " Meeting",
            "url": self.get_absolute_url(),
            "body_text_template": """{{subject|safe}}""",
            "body_html_template": """{{subject}}""",
            "context": {
                "subject": mtg.subject,
                }
            }


class CommitteeMemberRole(enum.Enum):
    exofficio = enum.Item(1, 'Ex Officio')
    chairman = enum.Item(2, 'Chairman')
    ranking_member = enum.Item(3, 'Ranking Member')
    vice_chairman = enum.Item(4, 'Vice Chairman')
    member = enum.Item(5, 'Member')

class CommitteeMember(models.Model):
    
    # The parser wipes out this table each time it loads up
    # committee membership, so we should not create any
    # foreign keys to this model.
    
    person = models.ForeignKey('person.Person', related_name='committeeassignments')
    committee = models.ForeignKey('committee.Committee', related_name='members')
    role = models.IntegerField(choices=CommitteeMemberRole, default=CommitteeMemberRole.member)

    def __unicode__(self):
        return '%s @ %s as %s' % (self.person, self.committee, self.get_role_display())
        
    def role_name(self):
        return CommitteeMemberRole.by_value(self.role).label
        
    def subcommittee_role(self):
        try:
            return CommitteeMember.objects.filter(committee__committee=self.committee, person=self.person, role=CommitteeMemberRole.chairman)[0]
        except IndexError:
            return None
            
    def role_name_2(self):
        if self.role in (CommitteeMemberRole.member, CommitteeMemberRole.exofficio):
            return "a member of"
        else:
            return "the %s of" % self.role_name().lower()

MEMBER_ROLE_WEIGHTS = {
    CommitteeMemberRole.chairman: 5,
    CommitteeMemberRole.vice_chairman: 4,
    CommitteeMemberRole.ranking_member: 3,
    CommitteeMemberRole.exofficio: 2,
    CommitteeMemberRole.member: 1
}

class CommitteeMeeting(models.Model):
    # The parser wipes out this table each time it loads up
    # committee schedules, so we should not create any
    # foreign keys to this model.

    committee = models.ForeignKey('committee.Committee', related_name='meetings')
    when = models.DateTimeField()
    subject = models.TextField()
    bills = models.ManyToManyField('bill.Bill', blank=True)


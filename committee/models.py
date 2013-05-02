# -*- coding: utf-8 -*-
from django.db import models
from django.core.urlresolvers import reverse

from common import enum

class CommitteeType(enum.Enum):
    senate = enum.Item(1, 'Senate', abbrev="S")
    joint = enum.Item(2, 'Joint', abbrev="J")
    house = enum.Item(3, 'House', abbrev="H")


class Committee(models.Model):
    """Committees and subcommittees in the United States Congress, including historical committees."""

    # committee_type applies to committees but not subcommittees
    committee_type = models.IntegerField(choices=CommitteeType, blank=True, null=True, help_text="Whether this is a House, Senate, or Joint committee.")
    code = models.CharField(max_length=10, help_text="An alphanumeric code used for the committee on THOMAS.gov, House.gov, and Senate.gov.")
    name = models.CharField(max_length=255, help_text="The name of the committee or subcommittee. Committee names typically look like '{House,Senate} Committee on ...', while subcommmittee names look like 'Legislative Branch'.")
    url = models.CharField(max_length=255, blank=True, null=True, help_text="The committee's website.")
    abbrev = models.CharField(max_length=255, blank=True, help_text="A really short abbreviation for the committee. Has no special significance.")
    obsolete = models.BooleanField(blank=True, default=False, db_index=True, help_text="True if this committee no longer exists.")
    committee = models.ForeignKey('self', blank=True, null=True, related_name='subcommittees', on_delete=models.PROTECT, help_text="This field indicates whether the object is a commmittee, in which case the committee field is null, or a subcommittee, in which case this field gives the parent committee.")

    def __unicode__(self):
        return self.name

    class Meta:
        ordering = ['name']

    # api
    api_recurse_on = ("committee",)
    api_example_id = 2650
    api_example_list = { "obsolete": "0" }

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
        feeds = [Feed.AllCommitteesFeed(), Feed.CommitteeMeetingsFeed(self.code)]
        if self.committee: feeds.append(Feed.CommitteeMeetingsFeed(self.committee.code)) # add parent committee
        with Event.update(self) as E:
            for meeting in self.meetings.all():
                E.add("mtg_" + str(meeting.id), meeting.when,
                	feeds + [Feed.BillFeed(b) for b in meeting.bills.all()])
    
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
    """A record indicating the current membership of a Member of Congress on a committee or subcommittee.
    The IDs on these records are not stable (do not use them)."""
    
    # The parser wipes out this table each time it loads up
    # committee membership, so we should not create any
    # foreign keys to this model.
    
    person = models.ForeignKey('person.Person', related_name='committeeassignments', help_text="The Member of Congress serving on a committee.")
    committee = models.ForeignKey('committee.Committee', related_name='members', help_text="The committee or subcommittee being served on.")
    role = models.IntegerField(choices=CommitteeMemberRole, default=CommitteeMemberRole.member, help_text="The role of the member on the committee.")

    def __unicode__(self):
        return '%s @ %s as %s' % (self.person, self.committee, self.get_role_display())
        
    # api
    api_recurse_on = ("committee","person")
    
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

    created = models.DateTimeField(auto_now_add=True)
    committee = models.ForeignKey('committee.Committee', related_name='meetings')
    when = models.DateTimeField()
    subject = models.TextField()
    bills = models.ManyToManyField('bill.Bill', blank=True)
    guid = models.CharField(max_length=36, db_index=True, unique=True)
    

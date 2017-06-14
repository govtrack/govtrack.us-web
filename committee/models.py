# -*- coding: utf-8 -*-
from django.db import models
from django.core.urlresolvers import reverse

from datetime import datetime, timedelta
import re

from common import enum

from settings import CURRENT_CONGRESS

class CommitteeType(enum.Enum):
    senate = enum.Item(1, 'Senate', abbrev="S")
    joint = enum.Item(2, 'Joint', abbrev="J")
    house = enum.Item(3, 'House', abbrev="H")


class Committee(models.Model):
    """Committees and subcommittees in the United States Congress, including historical committees."""

    # committee_type applies to committees but not subcommittees
    committee_type = models.IntegerField(choices=CommitteeType, blank=True, null=True, help_text="Whether this is a House, Senate, or Joint committee.")
    code = models.CharField(max_length=10, db_index=True, unique=True, help_text="An alphanumeric code used for the committee on THOMAS.gov, House.gov, and Senate.gov.")
    name = models.CharField(max_length=255, help_text="The name of the committee or subcommittee. Committee names typically look like '{House,Senate} Committee on ...', while subcommmittee names look like 'Legislative Branch'.")
    url = models.CharField(max_length=255, blank=True, null=True, help_text="The committee's website.")
    abbrev = models.CharField(max_length=255, blank=True, help_text="A really short abbreviation for the committee. Has no special significance.")
    obsolete = models.BooleanField(blank=True, default=False, db_index=True, help_text="True if this committee no longer exists.")
    committee = models.ForeignKey('self', blank=True, null=True, related_name='subcommittees', on_delete=models.PROTECT, help_text="This field indicates whether the object is a commmittee, in which case the committee field is null, or a subcommittee, in which case this field gives the parent committee.")
    jurisdiction = models.TextField(blank=True, null=True, help_text="The committee's jurisdiction, if known.")
    jurisdiction_link = models.TextField(blank=True, null=True, help_text="A link to where the jurisdiction text was sourced from.")

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
            return reverse('subcommittee_details', args=[parent.code, self.code[4:]])
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
    def shortname2(self):
        return self.name.replace("Committee on the ", "").replace("Committee on ", "").replace("Subcommittee on ", "")

    def sortname(self, with_chamber=False):
        if self.committee:
            return self.committee.sortname(with_chamber) + ": " + self.name.replace("Subcommittee on the ", "").replace("Subcommittee on ", "")

        m = re.match("(House|Senate|Joint) ((Select|Special|Permanent Select) )?Committee on (the )?(.+)", self.name)
        if not m: return self.name # unrecognized format
        return \
              ((self.committee.sortname + " ") if self.committee else "") \
            + ((m.group(1) + " ") if with_chamber else "") \
            + m.group(5)

    @property
    def name_no_article(self):
            n = self.name
            if n.startswith("the "): n = n[4:]
            return n

    def committee_type_label(self):
        try:
            return CommitteeType.by_value(self.committee_type).label
        except enum.NotFound:
            return ""

    def committee_type_abbrev(self):
        return CommitteeType.by_value(self.committee_type).abbrev

    def has_current_bills(self):
        return self.bills.filter(congress=CURRENT_CONGRESS).exists()
    def current_bills_sorted(self):
        from haystack.query import SearchQuerySet
        qs = SearchQuerySet().using("bill").filter(indexed_model_name__in=["Bill"], congress=CURRENT_CONGRESS, committees=self.id).order_by('-proscore')
        return {
            "count": qs.count(),
            "bills": [ b.object for b in qs[0:100] ],
            }

    def get_feed(self, feed_type=""):
        if feed_type not in ("", "bills", "meetings"): raise ValueError(feed_type)
        from events.models import Feed
        return Feed.objects.get_or_create(feedname="committee%s:%s" % (feed_type, self.code))[0]

    @staticmethod
    def from_feed(feed, test=False):
        if ":" not in feed.feedname or feed.feedname.split(":")[0] not in ("committee", "committeebills", "committeemeetings"): raise ValueError(feed.feedname)
        try:
            return Committee.objects.get(code=feed.feedname.split(":")[1])
        except Committee.DoesNotExist:
            if test: return False
            raise ValueError(feed.feedname)

    @staticmethod
    def AllCommitteesFeed():
        from events.models import Feed
        return Feed.get_noarg_feed("misc:allcommittee")
    
    def create_events(self):
        from events.models import Feed, Event
        feeds = [Committee.AllCommitteesFeed(), self.get_feed("meetings")]
        if self.committee: feeds.append(self.committee.get_feed("meetings")) # add parent committee
        with Event.update(self) as E:
            for meeting in self.meetings.all():
                E.add("mtg_" + str(meeting.id), meeting.when,
                	feeds + [b.get_feed() for b in meeting.bills.all()])

    def render_event(self, eventid, feeds):
        eventinfo = eventid.split("_")
        mtg = CommitteeMeeting.objects.get(id=eventinfo[1])

        return {
            "type": "Committee Meeting",
            "date": mtg.when,
            "title": self.fullname + " Meeting",
            "url": self.get_absolute_url(),
            "body_text_template": """{{subject|safe}}""",
            "body_html_template": """<p>{{subject}}</p>""",
            "context": {
                "subject": mtg.subject + (" (Location: " + mtg.room + ")" if mtg.room else ""),
                }
            }


class CommitteeMemberRole(enum.Enum):
    exofficio = enum.Item(1, 'Ex Officio')
    chair = enum.Item(2, 'Chair')
    ranking_member = enum.Item(3, 'Ranking Member')
    vice_chair = enum.Item(4, 'Vice Chair')
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
        scr = CommitteeMember.objects.filter(committee__committee=self.committee, person=self.person).exclude(role=CommitteeMemberRole.member)
        try:
            return max(scr, key = lambda r : MEMBER_ROLE_WEIGHTS[r.role])
        except ValueError:
            return None

    def role_name_2(self):
        if self.role in (CommitteeMemberRole.member, CommitteeMemberRole.exofficio):
            return "a member of"
        else:
            return "the %s of" % self.role_name().lower()

MEMBER_ROLE_WEIGHTS = {
    CommitteeMemberRole.chair: 5,
    CommitteeMemberRole.vice_chair: 4,
    CommitteeMemberRole.ranking_member: 3,
    CommitteeMemberRole.exofficio: 2,
    CommitteeMemberRole.member: 1
}

class CommitteeMeeting(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    committee = models.ForeignKey(Committee, related_name="meetings", db_index=True)
    when = models.DateTimeField()
    subject = models.TextField()
    bills = models.ManyToManyField("bill.Bill", blank=True)
    guid = models.CharField(max_length=36, db_index=True, unique=True)
    room = models.TextField(null=True)

    class Meta:
        ordering = [ "-created" ]

    def __unicode__(self):
        return self.guid

    @property
    def is_recently_added(self):
        return (self.created > (datetime.now() - timedelta(hours=36)))

    def abbrev_committee_name(self):
        return self.committee.sortname(True)

# feeds

from events.models import Feed, truncate_words
Feed.register_feed(
    "misc:allcommittee",
    title = "Committee Meetings",
    link = "/congress/committees",
    simple = True,
    sort_order = 103,
    category = "federal-committees",
    description = "Get an alert whenever a committee hearing or mark-up session is scheduled.",
    )
Feed.register_feed(
    "committee:",
    title = lambda feed : truncate_words(Committee.from_feed(feed).fullname, 12),
    noun = "committee",
    includes = lambda feed : [Committee.from_feed(feed).get_feed("bills"), Committee.from_feed(feed).get_feed("meetings")],
    link = lambda feed: Committee.from_feed(feed).get_absolute_url(),
    scoped_title = lambda feed : "All Events for This Committee",
    is_valid = lambda feed : Committee.from_feed(feed, test=True),
    category = "federal-committees",
    description = "You will get updates about major activity on bills referred to this commmittee plus notices of scheduled hearings and mark-up sessions.",
    )
Feed.register_feed(
    "committeebills:",
    title = lambda feed : "Bills in " + truncate_words(Committee.from_feed(feed).fullname, 12),
    noun = "committee",
    link = lambda feed: Committee.from_feed(feed).get_absolute_url(),
    scoped_title = lambda feed : "Activity on This Committee's Bills",
    category = "federal-committees",
    description = "You will get updates about major activity on bills referred to this commmittee.",
    )
Feed.register_feed(
    "committeemeetings:",
    title = lambda feed : "Meetings for " + truncate_words(Committee.from_feed(feed).fullname, 12),
    noun = "committee",
    link = lambda feed: Committee.from_feed(feed).get_absolute_url(),
    scoped_title = lambda feed : "This Committee's Hearings and Markups",
    single_event_type = True,
    category = "federal-committees",
    description = "You will get notices for this committee's scheduled hearings and mark-up sessions.",
    )

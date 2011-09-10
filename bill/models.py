# -*- coding: utf-8 -*-
from django.db import models

from common import enum
from common.fields import JSONField

from committee.models import Committee
from bill.status import BillStatus

from django.conf import settings

from django.core.urlresolvers import reverse

"Enums"

class BillType(enum.Enum):
    house_resolution = enum.Item(1, 'H.Res.', slug='hres', xml_code='hr')
    senate = enum.Item(2, 'S.', slug='s', xml_code='s')
    house_of_representatives = enum.Item(3, 'H.R.', slug='hr', xml_code='h')
    senate_resolution = enum.Item(4, 'S.Res.', slug='sr', xml_code='sr')
    house_concurrent_resolution = enum.Item(5, 'H.Con.Res.', slug='hc', xml_code='hc')
    senate_concurrent_resolution = enum.Item(6, 'S.Con.Res.', slug='sc', xml_code='sc')
    house_joint_resolution = enum.Item(7, 'H.J.Res.', slug='hj', xml_code='hj')
    senate_joint_resolution = enum.Item(8, 'S.J.Res.', slug='sj', xml_code='sj')


class TermType(enum.Enum):
    old = enum.Item(1, 'Old')
    new = enum.Item(2, 'New')

"Models"

class BillTerm(models.Model):
    """
    Bill Term aka Issua Area

    Old terms:
     * http://www.govtrack.us/data/us/liv.xml
    New terms:
     * http://www.govtrack.us/data/us/liv111.xml
     * http://www.govtrack.us/data/us/crsnet.xml
    """
    name = models.CharField(max_length=255)
    parent = models.ForeignKey('bill.BillTerm', blank=True, null=True)
    term_type = models.IntegerField(choices=TermType)

    def __unicode__(self):
        return self.name

    class Meta:
        unique_together = ('name', 'parent', 'term_type')


class Cosponsor(models.Model):
    person = models.ForeignKey('person.Person')
    bill = models.ForeignKey('bill.Bill')
    joined = models.DateField()
    withdrawn = models.DateField(blank=True, null=True)


class Bill(models.Model):
    title = models.CharField(max_length=255)
    # Serialized list of all bill titles
    titles = JSONField()
    bill_type = models.IntegerField(choices=BillType)
    congress = models.IntegerField()
    number = models.IntegerField()
    sponsor = models.ForeignKey('person.Person', blank=True, null=True,
                                related_name='sponsored_bills')
    committees = models.ManyToManyField(Committee, related_name='bills')
    terms = models.ManyToManyField(BillTerm, related_name='bills')
    current_status = models.IntegerField(choices=BillStatus)
    current_status_date = models.DateField()
    introduced_date = models.DateField()
    cosponsors = models.ManyToManyField('person.Person', blank=True, through='bill.Cosponsor')

    def __unicode__(self):
        return self.title
        
    def get_absolute_url(self):
        return "/congress/bills/%d/%s%d" % (self.congress, self.bill_type, self.number)

    class Meta:
        ordering = ('congress', 'bill_type', 'number')
        unique_together = ('congress', 'bill_type', 'number')

    def get_status_text(self, status, date) :
        bill = self
        status = status.xml_code
        date = date.strftime("%B %d, %Y").replace(" 0", " ")
        
        # Some status messages depend on whether the bill is current:
        if bill.congress == settings.CURRENT_CONGRESS:
            if status == "INTRODUCED":
                status = "This bill or resolution is in the first stage of the legislative process. It was introduced into Congress on %s. Most bills and resolutions are assigned to committees which consider them before they move to the House or Senate as a whole."
            elif status == "REFERRED":
                status = "This bill or resolution was assigned to a congressional committee on %s, which will consider it before possibly sending it on to the House or Senate as a whole. The majority of bills never make it past this point."
            elif status == "REPORTED":
                status = "The committees assigned to this bill or resolution sent it to the House or Senate as a whole for consideration on %s."
            elif status == "PASS_OVER:HOUSE":
                status = "This bill or resolution passed in the House on %s and goes to the Senate next for consideration."
            elif status == "PASS_OVER:SENATE":
                status = "This bill or resolution passed in the Senate on %s and goes to the House next for consideration."
            elif status == "PASSED:BILL":
                status = "This bill passed by Congress on %s and goes to the President next."
            elif status == "PASS_BACK:HOUSE":
                status = "This bill or resolution passed in the Senate and the House, but the House made changes and sent it back to the Senate on %s."
            elif status == "PASS_BACK:SENATE":
                status = "This bill or resolution has been passed in the House and the Senate, but the Senate made changes and sent it back to the House on %s."
            elif status == "PROV_KILL:SUSPENSIONFAILED":
                status = "This bill or resolution is provisionally dead due to a failed vote on %s under a fast-track procedure called \"suspension.\" It may or may not get another vote."
            elif status == "PROV_KILL:CLOTUREFAILED":
                status = "This bill or resolution is provisionally dead due to a failed vote for cloture, i.e. to stop a filibuster or threat of a filibuster, on %s."
            elif status == "PROV_KILL:PINGPONGFAIL":
                status = "This bill or resolution is provisionally dead due to a failed attempt to resolve differences between the House and Senate versions, on %s."
            elif status == "PROV_KILL:VETO":
                status = "This bill was vetoed by the President on %s. The bill is dead unless Congress can override it."
            elif status == "OVERRIDE_PASS_OVER:HOUSE":
                status = "After a presidential veto, the House succeeeded in an override on %s. It goes to the Senate next."
            elif status == "OVERRIDE_PASS_OVER:SENATE":
                status = "After a presidential veto, the Senate succeeded in an override on %s. It goes to the House next."
        
        else: # Bill is not current.
            if status == "INTRODUCED" or status == "REFERRED" or status == "REPORTED":
                status = "This bill or resolution was introduced on %s, in a previous session of Congress, but was not passed."
            elif status == "PASS_OVER:HOUSE":
                status = "This bill or resolution was introduced in a previous session of Congress and was passed by the House on %s but was never passed by the Senate."
            elif status == "PASS_OVER:SENATE":
                status = "This bill or resolution was introduced in a previous session of Congress and was passed by the Senate on %s but was never passed by the House."
            elif status == "PASSED:BILL":
                status = "This bill was passed by Congress on %s but was not enacted before the end of its Congressional session."
            elif status == "PASS_BACK:HOUSE" or status == "PASS_BACK:SENATE":
                status = "This bill or resolution was introduced in a previous session of Congress and though it was passed by both chambers on %s it was passed in non-identical forms and the differences were never resolved."
            elif status == "PROV_KILL:SUSPENSIONFAILED" or status == "PROV_KILL:CLOTUREFAILED" or status == "PROV_KILL:PINGPONGFAIL":
                status = "This bill or resolution was introduced in a previous session of Congress but was killed due to a failed vote for cloture, under a fast-track vote called \"suspension\", or while resolving differences on %s."
            elif status == "PROV_KILL:VETO":
                status = "This bill was vetoed by the President on %s and Congress did not attempt an override before the end of the Congressional session."
            elif status == "OVERRIDE_PASS_OVER:HOUSE" or status == "OVERRIDE_PASS_OVER:SENATE":
                status = "This bill was vetoed by the President and Congress did not finish an override begun on %s before the end of the Congressional session."
            
        # Some status messages do not depend on whether the bill is current.
        
        if status == "PASSED:SIMPLERES":
            status = "This simple resolution passed on %s. That is the end of the legislative process for a simple resolution."
        elif status == "PASSED:CONSTAMEND":
            status = "This proposal for a constitutional amendment passed Congress on %s and goes to the states for consideration next."
        elif status == "PASSED:CONCURRENTRES":
            status = "This concurrent resolution passed both chambers of Congress on %s. That is the end of the legislative process for concurrent resolutions. They do not have the force of law."
        elif status == "FAIL:ORIGINATING:HOUSE":
            status = "This bill or resolution failed in the House on %s."
        elif status == "FAIL:ORIGINATING:SENATE":
            status = "This bill or resolution failed in the Senate on %s."
        elif status == "FAIL:SECOND:HOUSE":
            status = "After passing in the Senate, this bill failed in the House on %s."
        elif status == "FAIL:SECOND:SENATE":
            status = "After passing in the House, this bill failed in the Senate on %s."
        elif status == "VETOED:OVERRIDE_FAIL_ORIGINATING:HOUSE" or status == "VETOED_OVERRIDE_FAIL_SECOND:HOUSE":
            status = "This bill was vetoed. The House attempted to override the veto on %s but failed."
        elif status == "VETOED:OVERRIDE_FAIL_ORIGINATING:SENATE" or status == "VETOED:OVERRIDE_FAIL_SECOND:SENATE":
            status = "This bill was vetoed. The Senate attempted to override the veto on %s but failed."
        elif status == "VETOED:POCKET":
            status = "This bill was pocket vetoed on %s."
        elif status == "ENACTED:SIGNED":
            status = "This bill was enacted after being signed by the President on %s."
        elif status == "ENACTED:VETO_OVERRIDE":
            status = "This bill was enacted after a congressional override of the President's veto on %s."
        
        return status % date

    def create_events(self, actions):
        from events.feeds import PersonSponsorshipFeed, BillFeed, IssueFeed, CommitteeFeed, ActiveBillsFeed, EnactedBillsFeed, IntroducedBillsFeed, ActiveBillsExceptIntroductionsFeed 
        from events.models import Event
        with Event.update(self) as E:
            index_feeds = [BillFeed(self)]
            if self.sponsor != None:
                index_feeds.append(PersonSponsorshipFeed(self.sponsor))
            index_feeds.extend([IssueFeed(ix) for ix in self.terms.all()])
            index_feeds.extend([CommitteeFeed(cx) for cx in self.committees.all()])
            
            E.add("state:" + str(BillStatus.introduced), self.introduced_date, index_feeds + [ActiveBillsFeed(), IntroducedBillsFeed()])
            for date, state, text in actions:
                if state == BillStatus.introduced:
                    continue # already indexed
                E.add("state:" + str(state), date, index_feeds + [ActiveBillsFeed(), ActiveBillsExceptIntroductionsFeed()])
    
    def render_event(self, eventid, feeds):
        
        from status import BillStatus
        ev_type, ev_code = eventid.split(":")
        
        status = BillStatus.by_value(int(ev_code))
        date = self.introduced_date
        action = None
       
        if status != BillStatus.introduced:
            from lxml import etree
            from parser.bill_parser import BillProcessor
            
            xml = etree.parse("data/us/%s/bills/%s%d.xml" % (self.congress, BillType.by_value(self.bill_type).xml_code, self.number))
            node = xml.xpath("actions/*[@state='%s']" % status.xml_code)[0]
            date = BillProcessor().parse_datetime(node.get("datetime"))
            action = node.xpath("string(text)")
            
            if node.tag in ("vote", "vote-aux") and node.get("how") == "roll":
                from vote.models import Vote, VoteCategory, CongressChamber
                from us import get_session_from_date
                try:
                    cn, sn = get_session_from_date(date)
                    vote = Vote.objects.get(congress=cn, session=sn, chamber=CongressChamber.house if node.get("where")=="h" else CongressChamber.senate, number=int(node.get("roll")))
                    cat = VoteCategory.by_value(int(vote.category))
                    if cat == VoteCategory.passage:
                        action = ""
                        second = ""
                    elif cat == VoteCategory.passage_suspension:
                        action = ""
                        second = " under \"suspension of the rules\""
                    else:
                        action = vote.question + ": "
                        second = ""
                    req = vote.required
                    if req == "1/2": req = "simple majority"
                    action += vote.result + " " + "%d/%d"%(vote.total_plus,vote.total_minus) + ", " + req + " required" + second + "."
                except Vote.DoesNotExist:
                    pass
        
        import events.feeds
        return {
            "type": "Bills and Resolutions",
            "date": date,
            "title": status.label + ": " + self.title,
            #"url": self.get_absolute_url(),
            "body_text_template":
"""{% if sponsor %}{{sponsor|safe}}{% endif %}
{% if action %}{{action|safe}}{% endif %}
{{summary|safe}}""",
            "body_html_template":
"""{% if sponsor %}<p>Sponsor: <a href="{{sponsor.get_absolute_url}}">{{sponsor}}</a></p>{% endif %}
{% if action %}<p>{{action}}</p>{% endif %}
<p>{{summary}}</p>
""",
            "context": {
                "sponsor": self.sponsor,
                "action": action,
                "summary": self.get_status_text(status, date),
                }
            }

    @models.permalink    
    def get_absolute_url(self):
        return ('bill_details', [self.congress,self.bill_type,self.number])

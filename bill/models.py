# -*- coding: utf-8 -*-
from django.db import models
from django.template.defaultfilters import slugify
from django.core.urlresolvers import reverse

from common import enum
from common.fields import JSONField

from committee.models import Committee
from bill.status import BillStatus
from bill.title import get_bill_number, get_primary_bill_title
from bill.billtext import load_bill_text

from django.conf import settings

import datetime, os.path
from lxml import etree

"Enums"

class BillType(enum.Enum):
    # slug must match regex for parse_bill_number
    senate_bill = enum.Item(2, 'S.', slug='s', xml_code='s', full_name="Senate bill", search_help_text="Senate bills")
    house_bill = enum.Item(3, 'H.R.', slug='hr', xml_code='h', full_name="House bill", search_help_text="House bills")
    senate_resolution = enum.Item(4, 'S.Res.', slug='sres', xml_code='sr', full_name="Senate simple resolution", search_help_text="Senate simple resolutions, which do not have the force of law")
    house_resolution = enum.Item(1, 'H.Res.', slug='hres', xml_code='hr', full_name="House simple resolution", search_help_text="House simple resolutions, which do not have the force of law")
    senate_concurrent_resolution = enum.Item(6, 'S.Con.Res.', slug='sconres', full_name="Senate concurrent resolution", xml_code='sc', search_help_text="Concurrent resolutions originating in the Senate, which do not have the force of law")
    house_concurrent_resolution = enum.Item(5, 'H.Con.Res.', slug='hconres', full_name="House concurrent resolution", xml_code='hc', search_help_text="Concurrent resolutions originating in the House, which do not have the force of law")
    senate_joint_resolution = enum.Item(8, 'S.J.Res.', slug='sjres', xml_code='sj', full_name="Senate joint resolution", search_help_text="Joint resolutions originating in the Senate, which may be used to enact laws or propose constitutional amendments")
    house_joint_resolution = enum.Item(7, 'H.J.Res.', slug='hjres', xml_code='hj', full_name="House joint resolution", search_help_text="Joint resolutions originating in the House, which may be used to enact laws or propose constitutional amendments")


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
    term_type = models.IntegerField(choices=TermType)
    name = models.CharField(max_length=255)
    subterms = models.ManyToManyField('self', related_name="parents", symmetrical=False)

    def __unicode__(self):
        return self.name
    def __repr__(self):
        return "<BillTerm: %s:%s>" % (TermType.by_value(self.term_type).label, self.name)
        
    class Meta:
        unique_together = ('name', 'term_type')

    def is_top_term(self):
        return self.parents.count() == 0

    def get_absolute_url(self):
        return "/congress/bills/subjects/%s/%d" % (slugify(self.name).replace('-', '_'), self.id)

class Cosponsor(models.Model):
    person = models.ForeignKey('person.Person')
    bill = models.ForeignKey('bill.Bill')
    joined = models.DateField()
    withdrawn = models.DateField(blank=True, null=True)
    class Meta:
        unique_together = [("bill", "person"),]
        
    _role = None
    def get_person_role(self):
        if not self._role:
            self._role = self.person.get_role_at_date(self.joined)
        return self._role

class Bill(models.Model):
    title = models.CharField(max_length=255, help_text="The bill's primary display title, including its number.")
    titles = JSONField() # serialized list of all bill titles as (type, as_of, text)
    bill_type = models.IntegerField(choices=BillType, help_text="The bill's type (e.g. H.R., S., H.J.Res. etc.)")
    congress = models.IntegerField(help_text="The number of the Congress in which the bill was introduced.")
    number = models.IntegerField(help_text="The bill's number (just the integer part).")
    sponsor = models.ForeignKey('person.Person', blank=True, null=True,
                                related_name='sponsored_bills', help_text="The primary sponsor of the bill.")
    committees = models.ManyToManyField(Committee, related_name='bills')
    terms = models.ManyToManyField(BillTerm, related_name='bills')
    current_status = models.IntegerField(choices=BillStatus, help_text="The current status of the bill.")
    current_status_date = models.DateField(help_text="The date of the last major action on the bill corresponding to the current_status.")
    introduced_date = models.DateField(help_text="The date the bill was introduced.")
    cosponsors = models.ManyToManyField('person.Person', blank=True, through='bill.Cosponsor', help_text="The bill's cosponsors.")
    docs_house_gov_postdate = models.DateTimeField(blank=True, null=True, help_text="The date on which the bill was posted to http://docs.house.gov (which is different from the date it was expected to be debated).")
    senate_floor_schedule_postdate = models.DateTimeField(blank=True, null=True, help_text="The date on which the bill was posted on the Senate Floor Schedule (which is different from the date it was expected to be debated.")
    major_actions = JSONField() # serialized list of all major actions (date/datetime, BillStatus, description)

    class Meta:
        ordering = ('congress', 'bill_type', 'number')
        unique_together = ('congress', 'bill_type', 'number')
        
    def __unicode__(self):
        return self.title
        
    #@models.permalink    
    def get_absolute_url(self):
        return reverse('bill_details', args=(self.congress, BillType.by_value(self.bill_type).slug, self.number))
        
    # indexing
    def get_index_text(self):
        return "\n".join([self.title] + [t[2] for t in self.titles]) \
        	+ "\n\n" + load_bill_text(self, None, plain_text=True)
    haystack_index = ('bill_type', 'congress', 'number', 'sponsor', 'current_status', 'terms', 'introduced_date', 'current_status_date')
    #haystack_index_extra = (('total_bets', 'Integer'),)
    def get_terms_index_list(self):
        return [t.id for t in self.terms.all().distinct()]
    #def total_bets(self):
    #    from website.models import TestMarketVote
    #    return TestMarketVote.objects.filter(bill=self).count()
    #######

        
    @property
    def display_number(self):
    	"""The bill's number, suitable for display, e.g. H.R. 1234. If the bill is for a past session of Congress, includes the Congress number."""
        return get_bill_number(self)
    @property
    def display_number_no_congress_number(self):
    	"""The bill's number, suitable for display, e.g. H.R. 1234."""
        return get_bill_number(self, show_congress_number="NONE")
    @property
    def display_number_with_congress_number(self):
        return get_bill_number(self, show_congress_number="ALL")

    @property
    def title_no_number(self):
    	"""The title of the bill without the number."""
        return get_primary_bill_title(self, self.titles, with_number=False)
        
    @property
    def bill_type_slug(self):
        return BillType.by_value(self.bill_type).slug
    @property
    def bill_type_name(self):
        return BillType.by_value(self.bill_type).full_name
    @property
    def noun(self):
    	"""The appropriate noun to use to refer to this instance, either 'bill' or 'resolution'."""
        return "bill" if self.bill_type in (BillType.house_bill, BillType.senate_bill) else "resolution"
    @property
    def originating_chamber(self):
        return "House" if self.bill_type in (BillType.house_bill, BillType.house_resolution, BillType.house_joint_resolution, BillType.house_concurrent_resolution) else "Senate"
    @property
    def opposite_chamber(self):
        return "Senate" if self.bill_type in (BillType.house_bill, BillType.house_resolution, BillType.house_joint_resolution, BillType.house_concurrent_resolution) else "House"

    @property
    def cosponsor_count(self):
        return self.cosponsor_records.filter(withdrawn=None).count()
    @property
    def cosponsor_records(self):
        return Cosponsor.objects.filter(bill=self).order_by('joined', 'person__lastname', 'person__firstname')

    @property
    def current_status_description(self):
    	"""Descriptive text for the bill's current status."""
        return self.get_status_text(self.current_status, self.current_status_date)

    @property
    def is_current(self):
    	"""Whether the bill was introduced in the current session of Congress."""
        return self.congress == settings.CURRENT_CONGRESS
    @property
    def is_alive(self):
    	"""Whether the bill was introduced in the current session of Congress and the bill's status is not a final status (i.e. can take no more action like a failed vote)."""
        return self.congress == settings.CURRENT_CONGRESS and self.current_status not in BillStatus.final_status

    def get_formatted_summary(self):
        return get_formatted_bill_summary(self)

    def get_status_text(self, status, date) :
        bill = self
        status = BillStatus.by_value(status).xml_code
        date = date.strftime("%B %d, %Y").replace(" 0", " ")
        
        # Some status messages depend on whether the bill is current:
        if bill.congress == settings.CURRENT_CONGRESS:
            if status == "INTRODUCED":
                status = "This %s is in the first stage of the legislative process. It was introduced into Congress on %s. It will typically be considered by committee next."
            elif status == "REFERRED":
                status = "This %s was assigned to a congressional committee on %s, which will consider it before possibly sending it on to the House or Senate as a whole."
            elif status == "REPORTED":
                status = "The committees assigned to this %s sent it to the House or Senate as a whole for consideration on %s."
            elif status == "PASS_OVER:HOUSE":
                status = "This %s passed in the House on %s and goes to the Senate next for consideration."
            elif status == "PASS_OVER:SENATE":
                status = "This %s passed in the Senate on %s and goes to the House next for consideration."
            elif status == "PASSED:BILL":
                status = "This %s was passed by Congress on %s and goes to the President next."
            elif status == "PASS_BACK:HOUSE":
                status = "This %s passed in the Senate and the House, but the House made changes and sent it back to the Senate on %s."
            elif status == "PASS_BACK:SENATE":
                status = "This %s has been passed in the House and the Senate, but the Senate made changes and sent it back to the House on %s."
            elif status == "PROV_KILL:SUSPENSIONFAILED":
                status = "This %s is provisionally dead due to a failed vote on %s under a fast-track procedure called \"suspension.\" It may or may not get another vote."
            elif status == "PROV_KILL:CLOTUREFAILED":
                status = "This %s is provisionally dead due to a failed vote for cloture on %s. Cloture is required to move past a Senate filibuster or the threat of a filibuster and takes a 3/5ths vote. In practice, most bills must pass cloture to move forward in the Senate."
            elif status == "PROV_KILL:PINGPONGFAIL":
                status = "This %s is provisionally dead due to a failed attempt to resolve differences between the House and Senate versions, on %s."
            elif status == "PROV_KILL:VETO":
                status = "This %s was vetoed by the President on %s. The bill is dead unless Congress can override it."
            elif status == "OVERRIDE_PASS_OVER:HOUSE":
                status = "After a presidential veto of the %s, the House succeeeded in an override on %s. It goes to the Senate next."
            elif status == "OVERRIDE_PASS_OVER:SENATE":
                status = "After a presidential veto of the %s, the Senate succeeded in an override on %s. It goes to the House next."
        
        else: # Bill is not current.
            if status == "INTRODUCED" or status == "REFERRED" or status == "REPORTED":
                status = "This %s was introduced on %s, in a previous session of Congress, but was not enacted."
            elif status == "PASS_OVER:HOUSE":
                status = "This %s was introduced in a previous session of Congress and was passed by the House on %s but was never passed by the Senate."
            elif status == "PASS_OVER:SENATE":
                status = "This %s was introduced in a previous session of Congress and was passed by the Senate on %s but was never passed by the House."
            elif status == "PASSED:BILL":
                status = "This %s was passed by Congress on %s but was not enacted before the end of its Congressional session."
            elif status == "PASS_BACK:HOUSE" or status == "PASS_BACK:SENATE":
                status = "This %s was introduced in a previous session of Congress and though it was passed by both chambers on %s it was passed in non-identical forms and the differences were never resolved."
            elif status == "PROV_KILL:SUSPENSIONFAILED" or status == "PROV_KILL:CLOTUREFAILED" or status == "PROV_KILL:PINGPONGFAIL":
                status = "This %s was introduced in a previous session of Congress but was killed due to a failed vote for cloture, under a fast-track vote called \"suspension\", or while resolving differences on %s."
            elif status == "PROV_KILL:VETO":
                status = "This %s was vetoed by the President on %s and Congress did not attempt an override before the end of the Congressional session."
            elif status == "OVERRIDE_PASS_OVER:HOUSE" or status == "OVERRIDE_PASS_OVER:SENATE":
                status = "This %s was vetoed by the President and Congress did not finish an override begun on %s before the end of the Congressional session."
            
        # Some status messages do not depend on whether the bill is current.
        
        if status == "PASSED:SIMPLERES":
            status = "This simple %s passed on %s. That is the end of the legislative process for a simple resolution."
        elif status == "PASSED:CONSTAMEND":
            status = "This %s proposing a constitutional amendment passed Congress on %s and goes to the states for consideration next."
        elif status == "PASSED:CONCURRENTRES":
            status = "This concurrent %s passed both chambers of Congress on %s. That is the end of the legislative process for concurrent resolutions. They do not have the force of law."
        elif status == "FAIL:ORIGINATING:HOUSE":
            status = "This %s failed in the House on %s."
        elif status == "FAIL:ORIGINATING:SENATE":
            status = "This %s failed in the Senate on %s."
        elif status == "FAIL:SECOND:HOUSE":
            status = "After passing in the Senate, this %s failed in the House on %s."
        elif status == "FAIL:SECOND:SENATE":
            status = "After passing in the House, this %s failed in the Senate on %s."
        elif status == "VETOED:OVERRIDE_FAIL_ORIGINATING:HOUSE" or status == "VETOED_OVERRIDE_FAIL_SECOND:HOUSE":
            status = "This %s was vetoed. The House attempted to override the veto on %s but failed."
        elif status == "VETOED:OVERRIDE_FAIL_ORIGINATING:SENATE" or status == "VETOED:OVERRIDE_FAIL_SECOND:SENATE":
            status = "This %s was vetoed. The Senate attempted to override the veto on %s but failed."
        elif status == "VETOED:POCKET":
            status = "This %s was pocket vetoed on %s."
        elif status == "ENACTED:SIGNED":
            status = "This %s was enacted after being signed by the President on %s."
        elif status == "ENACTED:VETO_OVERRIDE":
            status = "This %s was enacted after a congressional override of the President's veto on %s."
        
        return status % (self.noun, date)

    def thomas_link(self):
    	"""Returns the URL for the bill page on http://thomas.loc.gov."""
        return "http://thomas.loc.gov/cgi-bin/bdquery/z?d%d:%s%d:" \
            % (self.congress, self.bill_type_slug, self.number)

    def create_events(self):
        if self.congress < 111: return # not interested, creates too much useless data and slow to load
        from events.models import Feed, Event
        with Event.update(self) as E:
            # collect the feeds that we'll add major actions to
            bill_feed = Feed.BillFeed(self)
            index_feeds = [bill_feed]
            if self.sponsor != None:
                index_feeds.append(Feed.PersonSponsorshipFeed(self.sponsor))
            index_feeds.extend([Feed.IssueFeed(ix) for ix in self.terms.all()])
            index_feeds.extend([Feed.CommitteeBillsFeed(cx) for cx in self.committees.all()])
            
            # generate events for major actions
            E.add("state:" + str(BillStatus.introduced), self.introduced_date, index_feeds + [Feed.ActiveBillsFeed(), Feed.IntroducedBillsFeed()])
            common_feeds = [Feed.ActiveBillsFeed(), Feed.ActiveBillsExceptIntroductionsFeed()]
            enacted_feed = [Feed.EnactedBillsFeed()]
            for datestr, state, text in self.major_actions:
                if state == BillStatus.introduced:
                    continue # already indexed
                date = eval(datestr)
                E.add("state:" + str(state), date, index_feeds + common_feeds + (enacted_feed if state in BillStatus.final_status_passed_bill else []))
                
            # generate events for new cosponsors... group by join date, and
            # assume that join dates we've seen don't have new cosponsors
            # added later, or else we may miss that in an email update. we
            # don't actually need the people listed here, just the unique join
            # dates.
            cosponsor_join_dates = set()
            for cosp in Cosponsor.objects.filter(bill=self, withdrawn=None).exclude(joined=self.introduced_date):
                cosponsor_join_dates.add(cosp.joined)
            for joindate in cosponsor_join_dates:
                E.add("cosp:" + joindate.isoformat(), joindate, [bill_feed])
                
            # generate an event for appearing on docs.house.gov or the senate floor schedule:
            if self.docs_house_gov_postdate:
                E.add("dhg", self.docs_house_gov_postdate, index_feeds + common_feeds + [Feed.ComingUpFeed()])
            if self.senate_floor_schedule_postdate:
                E.add("sfs", self.senate_floor_schedule_postdate, index_feeds + common_feeds + [Feed.ComingUpFeed()])
    
    def render_event(self, eventid, feeds):
        if eventid in "dhg":
            return self.render_event_dhg(feeds)
        if eventid in "sfs":
            return self.render_event_sfs(feeds)
            
        ev_type, ev_code = eventid.split(":")
        if ev_type == "state":
            return self.render_event_state(ev_code, feeds)
        elif ev_type == "cosp":
            return self.render_event_cosp(ev_code, feeds)
        else:
            raise Exception()
          
    def render_event_state(self, ev_code, feeds):
        from status import BillStatus
        status = BillStatus.by_value(int(ev_code))
        date = self.introduced_date
        action = None
        action_type = None
       
        if status == BillStatus.introduced:
            action_type = "Introduced"
        else:
            for datestr, st, text in self.major_actions:
                if st == status:
                    date = eval(datestr)
                    action = text
                    break
            else:
                raise Exception("Invalid event.")
                
            if status not in (BillStatus.introduced, BillStatus.referred, BillStatus.reported):
                from lxml import etree
                from parser.bill_parser import BillProcessor
                
                xml = etree.parse("data/us/%s/bills/%s%d.xml" % (self.congress, BillType.by_value(self.bill_type).xml_code, self.number))
                node = xml.xpath("actions/*[@state='%s']" % status.xml_code)[0]
                
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
        

        return {
            "type": status.label,
            "date": date,
            "date_has_no_time": isinstance(date, datetime.date),
            "title": self.title,
            "url": self.get_absolute_url(),
            "body_text_template":
"""{% if sponsor %}Sponsor: {{sponsor|safe}}{% endif %}
{% if action %}{{action|safe}}{% endif %}
{{summary|safe}}""",
            "body_html_template":
"""{% if sponsor %}<p>Sponsor: <a href="{{SITE_ROOT}}{{sponsor.get_absolute_url}}">{{sponsor}}</a></p>{% endif %}
{% if action %}<p>{{action}}</p>{% endif %}
<p>{{summary}}</p>
""",
            "context": {
                "sponsor": self.sponsor,
                "action": action,
                "summary": self.get_status_text(status, date),
                }
            }

    def render_event_cosp(self, ev_code, feeds):
        cosp = Cosponsor.objects.filter(bill=self, withdrawn=None, joined=ev_code)
        if len(cosp) == 0:
            # What to do if there are no longer new cosponsors on this date?
            # TODO test this.
            return {
                "type": "New Cosponsors",
                "date": datetime.date(*ev_code.split('-')),
                "date_has_no_time": True,
                "title": self.title,
                "url": self.get_absolute_url(),
                "body_text_template": "Event error.",
                "body_html_template": "Event error.",
                "context": {},
                }
            
        return {
            "type": "New Cosponsor" + ("" if len(cosp) == 1 else "s"),
            "date": cosp[0].joined,
            "date_has_no_time": True,
            "title": self.title,
            "url": self.get_absolute_url(),
            "body_text_template":
"""{% for p in cosponsors %}{{ p.person.name }}
{% endfor %}""",
            "body_html_template": """{% for p in cosponsors %}<p><a href="{{SITE_ROOT}}{{p.person.get_absolute_url}}">{{ p.person.name }}</a></p>{% endfor %}""",
            "context": {
                "cosponsors": cosp,
                }
            }

    def render_event_dhg(self, feeds):
        return {
            "type": "Legislation Coming Up",
            "date": self.docs_house_gov_postdate,
            "date_has_no_time": False,
            "title": self.title,
            "url": self.get_absolute_url(),
            "body_text_template": """This {{noun}} has been added to the House's schedule for the coming week, according to the House Majority Leader. More information can be found at http://docs.house.gov.\n\n{{current_status}}""",
            "body_html_template": """<p>This {{noun}} has been added to the House&rsquo;s schedule for the coming week, according to the House Majority Leader. See <a href="http://docs.house.gov">the week ahead</a>.</p><p>{{current_status}}</p>""",
            "context": { "noun": self.noun, "current_status": self.current_status_description },
            }
    def render_event_sfs(self, feeds):
        return {
            "type": "Legislation Coming Up",
            "date": self.senate_floor_schedule_postdate,
            "date_has_no_time": False,
            "title": self.title,
            "url": self.get_absolute_url(),
            "body_text_template": """This {{noun}} has been added to the Senate's floor schedule for the next legislative day.\n\n{{current_status}}""",
            "body_html_template": """<p>This {{noun}} has been added to the Senate&rsquo;s floor schedule for the next legislative day.</p><p>{{current_status}}</p>""",
            "context": { "noun": self.noun, "current_status": self.current_status_description },
            }
        
    def get_major_events(self):
        ret = []
        saw_intro = False
        for datestr, st, text in self.major_actions:
            date = eval(datestr)
            if (st == BillStatus.passed_bill and self.bill_type in (BillType.senate_bill, BillType.senate_joint_resolution)) or (st == BillStatus.passed_concurrentres and self.bill_type == BillType.senate_concurrent_resolution):
                st = "Passed House"
            elif (st == BillStatus.passed_bill and self.bill_type in (BillType.house_bill, BillType.house_joint_resolution)) or (st == BillStatus.passed_concurrentres and self.bill_type == BillType.house_concurrent_resolution):
                st = "Passed Senate"
            else:
                if st == BillStatus.introduced: saw_intro = True
                st = BillStatus.by_value(st).label
            ret.append({
                "label": st,
                "date": date,
                "extra": text,
            })
        if not saw_intro: ret.insert(0, { "label": "Introduced", "date": self.introduced_date })
        return ret
    
    def get_future_events(self):
        # predict the major actions not yet occurred on the bill, based on its
        # current status.
        
        # define a state diagram
        common_paths = {
            BillStatus.introduced: BillStatus.referred,
            BillStatus.referred: BillStatus.reported,
        }
        
        type_specific_paths = {
            BillType.house_bill: {
                BillStatus.reported: BillStatus.pass_over_house,
                BillStatus.pass_over_house: (BillStatus.passed_bill, "Passed Senate"),
                BillStatus.pass_back_house: (BillStatus.passed_bill, "Senate Approves House Changes"),
                BillStatus.pass_back_senate: (BillStatus.passed_bill, "House Approves Senate Changes"),
                BillStatus.passed_bill: BillStatus.enacted_signed,
                BillStatus.prov_kill_suspensionfailed: BillStatus.pass_over_house, 
                BillStatus.prov_kill_cloturefailed: (BillStatus.passed_bill, "Passed Senate"),
                BillStatus.prov_kill_pingpongfail: (BillStatus.passed_bill, "Passed House/Senate"),
                BillStatus.prov_kill_veto: BillStatus.override_pass_over_house,
                BillStatus.override_pass_over_house: BillStatus.enacted_veto_override,
            },
            BillType.senate_bill: {
                BillStatus.reported: BillStatus.pass_over_senate,
                BillStatus.pass_over_senate: (BillStatus.passed_bill, "Passed House"),
                BillStatus.pass_back_house: (BillStatus.passed_bill, "Senate Approves House Changes"),
                BillStatus.pass_back_senate: (BillStatus.passed_bill, "House Approves Senate Changes"),
                BillStatus.passed_bill: BillStatus.enacted_signed,
                BillStatus.prov_kill_suspensionfailed: (BillStatus.passed_bill, "Passed House"), 
                BillStatus.prov_kill_cloturefailed: BillStatus.pass_over_senate,
                BillStatus.prov_kill_pingpongfail: (BillStatus.passed_bill, "Passed Senate/House"),
                BillStatus.prov_kill_veto: BillStatus.override_pass_over_senate,
                BillStatus.override_pass_over_senate: BillStatus.enacted_veto_override,
            },                
            BillType.house_resolution:  {
                BillStatus.reported: BillStatus.passed_simpleres,
                BillStatus.prov_kill_suspensionfailed: BillStatus.pass_over_house, 
            },
            BillType.senate_resolution: {
                BillStatus.reported: BillStatus.passed_simpleres,
                BillStatus.prov_kill_cloturefailed: BillStatus.passed_simpleres,
            },
            BillType.house_concurrent_resolution: {
                BillStatus.reported: BillStatus.pass_over_house,
                BillStatus.pass_over_house: (BillStatus.passed_concurrentres, "Passed Senate"),
                BillStatus.pass_back_house: (BillStatus.passed_concurrentres, "Senate Approves House Changes"),
                BillStatus.pass_back_senate: (BillStatus.passed_concurrentres, "House Approves Senate Changes"),
                BillStatus.prov_kill_suspensionfailed: BillStatus.pass_over_house, 
                BillStatus.prov_kill_cloturefailed: BillStatus.passed_concurrentres,
                BillStatus.prov_kill_pingpongfail: BillStatus.passed_concurrentres,
            },
            BillType.senate_concurrent_resolution: {
                BillStatus.reported: BillStatus.pass_over_senate,
                BillStatus.pass_over_senate: (BillStatus.passed_concurrentres, "Passed House"),
                BillStatus.pass_back_house: (BillStatus.passed_concurrentres, "Senate Approves House Changes"),
                BillStatus.pass_back_senate: (BillStatus.passed_concurrentres, "House Approves Senate Changes"),
                BillStatus.prov_kill_suspensionfailed: BillStatus.passed_concurrentres, 
                BillStatus.prov_kill_cloturefailed: BillStatus.pass_over_senate,
                BillStatus.prov_kill_pingpongfail: BillStatus.passed_concurrentres,
            },
            BillType.house_joint_resolution: { # assuming const amend
                BillStatus.reported: BillStatus.pass_over_house,
                BillStatus.pass_over_house: BillStatus.passed_constamend,
                BillStatus.pass_back_house: BillStatus.passed_constamend,
                BillStatus.pass_back_senate: BillStatus.passed_constamend,
                BillStatus.prov_kill_suspensionfailed: BillStatus.pass_over_house, 
                BillStatus.prov_kill_cloturefailed: BillStatus.passed_constamend,
                BillStatus.prov_kill_pingpongfail: BillStatus.passed_constamend,
            },
            BillType.senate_joint_resolution: { # assuming const amend
                BillStatus.reported: BillStatus.pass_over_senate,
                BillStatus.pass_over_senate: BillStatus.passed_constamend,
                BillStatus.pass_back_house: BillStatus.passed_constamend,
                BillStatus.pass_back_senate: BillStatus.passed_constamend,
                BillStatus.prov_kill_suspensionfailed: BillStatus.passed_constamend, 
                BillStatus.prov_kill_cloturefailed: BillStatus.pass_over_senate,
                BillStatus.prov_kill_pingpongfail: BillStatus.passed_constamend,
            }
        }
            
        bt = self.bill_type
        if bt == BillType.house_joint_resolution and not "Proposing an Amendment" in self.title: bt = BillType.house_bill
        if bt == BillType.senate_joint_resolution and not "Proposing an Amendment" in self.title: bt = BillType.senate_bill

        path = { }
        path.update(common_paths)
        path.update(type_specific_paths[bt])
        
        seq = []
        st = self.current_status
        while st in path:
            st = path[st]
            if type(st) == tuple:
                label = st[1]
                st = st[0]
            else:
                label = st.label
            seq.append(label)
            
        return seq
        
    def get_terms_sorted(self):
        terms = list(self.terms.all())
        terms.sort(key = lambda x : (not x.is_top_term(), x.name))
        return terms
        
    def get_related_bills(self):
        ret = []
        seen = set()
        bills = list(self.relatedbills.all().select_related("bill"))
        bills.sort(key = lambda rb : RelatedBill.relation_sort_order.get(rb.relation, 999))
        for rb in bills:
            if not rb.bill in seen:
                ret.append(rb)
                seen.add(rb.bill)
        return ret

    
    def get_open_market(self, user):
        from django.contrib.contenttypes.models import ContentType
        bill_ct = ContentType.objects.get_for_model(Bill)
        
        import predictionmarket.models
        try:
            m = predictionmarket.models.Market.objects.get(owner_content_type=bill_ct, owner_object_id=self.id, isopen=True)
        except predictionmarket.models.Market.DoesNotExist:
            return None
            
        for outcome in m.outcomes.all():
            if outcome.owner_key == "1": # "yes"
                m.yes = outcome
                m.yes_price = int(round(outcome.price() * 100.0))
        if user and user.is_authenticated():
            account = predictionmarket.models.TradingAccount.get(user, if_exists=True)
            if account:
                positions, profit = account.position_in_market(m)
                m.user_profit = round(profit, 1)
                m.user_positions = { }
                for outcome in positions:
                    m.user_positions[outcome.owner_key] = positions[outcome]
        return m
            
class RelatedBill(models.Model):
    bill = models.ForeignKey(Bill, related_name="relatedbills")
    related_bill = models.ForeignKey(Bill, related_name="relatedtobills")
    relation = models.CharField(max_length=16)
    
    relation_sort_order = { "identical": 0 }
    
def get_formatted_bill_summary(bill):
    sfn = "data/us/%d/bills.summary/%s%d.summary.xml" % (bill.congress, BillType.by_value(bill.bill_type).xml_code, bill.number)
    if not os.path.exists(sfn): return None
    
    dom = etree.parse(open(sfn))
    xslt_root = etree.XML('''
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <xsl:output omit-xml-declaration="yes"/>
    <xsl:template match="summary//Paragraph[string(.)!='']">
        <div style="margin-top: .5em; margin-bottom: .5em">
            <xsl:apply-templates/>
        </div>
    </xsl:template>

    <xsl:template match="Division|Title|Subtitle|Part|Chapter|Section">
        <xsl:if test="not(@number='meta')">
        <div>
            <xsl:choose>
            <xsl:when test="@name='' and count(*)=1">
            <div style="margin-top: .75em">
            <span xml:space="preserve" style="font-weight: bold;"><xsl:value-of select="name()"/> <xsl:value-of select="@number"/>.</span>
            <xsl:value-of select="Paragraph"/>
            </div>
            </xsl:when>

            <xsl:otherwise>
            <div style="font-weight: bold; margin-top: .75em" xml:space="preserve">
                <xsl:value-of select="name()"/>
                <xsl:value-of select="@number"/>
                <xsl:if test="not(@name='')"> - </xsl:if>
                <xsl:value-of select="@name"/>
            </div>
            <div style="margin-left: 2em">
                <xsl:apply-templates/>
            </div>
            </xsl:otherwise>
            </xsl:choose>
        </div>
        </xsl:if>
    </xsl:template>
</xsl:stylesheet>''')
    transform = etree.XSLT(xslt_root)
    summary = transform(dom)
    if unicode(summary).strip() == "":
        return None
    return summary


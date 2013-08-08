# -*- coding: utf-8 -*-
from django.db import models
from django.template.defaultfilters import slugify
from django.core.urlresolvers import reverse

from common import enum
from jsonfield import JSONField

from committee.models import Committee, CommitteeMeeting, CommitteeMember, MEMBER_ROLE_WEIGHTS
from bill.status import BillStatus, get_bill_status_string
from bill.title import get_bill_number, get_primary_bill_title
from bill.billtext import load_bill_text
from us import get_congress_dates

from django.conf import settings

import datetime, os.path, re, urlparse
from lxml import etree

"Enums"

class BillType(enum.Enum):
    # slug must match regex for parse_bill_number
    senate_bill = enum.Item(2, 'S.', slug='s', xml_code='s', full_name="Senate bill", search_help_text="Senate bills")
    house_bill = enum.Item(3, 'H.R.', slug='hr', xml_code='h', full_name="House of Representatives bill", search_help_text="House bills")
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
    subterms = models.ManyToManyField('self', related_name="parents", symmetrical=False, blank=True)

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
    """A (bill, person) pair indicating cosponsorship, with join and withdrawn dates."""
    
    person = models.ForeignKey('person.Person', db_index=True, on_delete=models.PROTECT, help_text="The cosponsoring person.")
    role = models.ForeignKey('person.PersonRole', db_index=True, on_delete=models.PROTECT, help_text="The role of the cosponsor at the time of cosponsorship.")
    bill = models.ForeignKey('bill.Bill', db_index=True, help_text="The bill being cosponsored.")
    joined = models.DateField(db_index=True, help_text="The date the cosponsor was added. It is always greater than or equal to the bill's introduced_date.")
    withdrawn = models.DateField(blank=True, null=True, help_text="If the cosponsor withdrew his/her support, the date of withdrawl. Otherwise empty.")
    class Meta:
        unique_together = [("bill", "person"),]

    api_example_parameters = { "sort": "-joined" }
    
    @property
    def person_name(self):
        # don't need title because it's implicit from the bill type
        from person.name import get_person_name
        return get_person_name(self.person, role_date=self.joined, firstname_position="after", show_title=False)
        
    # role is a new field which I added with (does not take into account people with overlapping roles such as going from House to Senate on the same day):
    #for role in PersonRole.objects.filter(startdate__lte="1970-01-01", startdate__gt="1960-01-01"):
    #    Cosponsor.objects.filter(
    #        person=role.person_id,
    #        joined__gte=role.startdate,
    #        joined__lte=role.enddate).update(role = role)
            
class Bill(models.Model):
    """A bill represents a bill or resolution introduced in the United States Congress."""
    
    title = models.CharField(max_length=255, help_text="The bill's primary display title, including its number.")
    titles = JSONField(default=None) # serialized list of all bill titles as (type, as_of, text)
    bill_type = models.IntegerField(choices=BillType, help_text="The bill's type (e.g. H.R., S., H.J.Res. etc.)")
    congress = models.IntegerField(help_text="The number of the Congress in which the bill was introduced. The current Congress is %d." % settings.CURRENT_CONGRESS)
    number = models.IntegerField(help_text="The bill's number (just the integer part).")
    sponsor = models.ForeignKey('person.Person', blank=True, null=True,
                                related_name='sponsored_bills', help_text="The primary sponsor of the bill.", on_delete=models.PROTECT)
    sponsor_role = models.ForeignKey('person.PersonRole', blank=True, null=True, help_text="The role of the primary sponsor of the bill at the time the bill was introduced.", on_delete=models.PROTECT)
    committees = models.ManyToManyField(Committee, related_name='bills', help_text="Committees to which the bill has been referred.")
    terms = models.ManyToManyField(BillTerm, related_name='bills', help_text="Subject areas associated with the bill.")
    current_status = models.IntegerField(choices=BillStatus, help_text="The current status of the bill.")
    current_status_date = models.DateField(help_text="The date of the last major action on the bill corresponding to the current_status.")
    introduced_date = models.DateField(help_text="The date the bill was introduced.")
    cosponsors = models.ManyToManyField('person.Person', blank=True, through='bill.Cosponsor', help_text="The bill's cosponsors.")
    docs_house_gov_postdate = models.DateTimeField(blank=True, null=True, help_text="The date on which the bill was posted to http://docs.house.gov (which is different from the date it was expected to be debated).")
    senate_floor_schedule_postdate = models.DateTimeField(blank=True, null=True, help_text="The date on which the bill was posted on the Senate Floor Schedule (which is different from the date it was expected to be debated).")
    major_actions = JSONField(default=[]) # serialized list of all major actions (date/datetime, BillStatus, description)
    
    sliplawpubpriv = models.CharField(max_length=3, choices=[("PUB", "Public"), ("PRI", "Private")], blank=True, null=True, help_text="For enacted laws, whether the law is a public (PUB) or private (PRI) law. Unique with congress and sliplawnum.")
    sliplawnum = models.IntegerField(blank=True, null=True, help_text="For enacted laws, the slip law number (i.e. the law number in P.L. XXX-123). Unique with congress and sliplawpublpriv.")
    #statutescite = models.CharField(max_length=16, blank=True, null=True, help_text="For enacted laws, a normalized U.S. Statutes at Large citation. Available only for years in which the Statutes at Large has already been published.")
    
    
    # role is a new field added with, but might not be perfect for overlapping roles (see Cosponsor)
    #for role in PersonRole.objects.filter(startdate__gt="1960-01-01"):
    #    Bill.objects.filter(
    #        sponsor=role.person_id,
    #        introduced_date__gte=role.startdate,
    #        introduced_date__lte=role.enddate).update(sponsor_role = role)
    
    class Meta:
        ordering = ('congress', 'bill_type', 'number')
        unique_together = [('congress', 'bill_type', 'number'),
        ('congress', 'sliplawpubpriv', 'sliplawnum')]
        
    def __unicode__(self):
        return self.title
        
    #@models.permalink    
    def get_absolute_url(self):
        return reverse('bill_details', args=(self.congress, BillType.by_value(self.bill_type).slug, self.number))
        
    # indexing
    def get_index_text(self):
        bill_text = load_bill_text(self, None, plain_text=True)
        if not bill_text: print "NO BILL TEXT", self
        return "\n".join([
            self.title,
            self.display_number_no_congress_number.replace(".", ""),
            self.display_number_no_congress_number.replace(".", "").replace(" ", ""),
            ] + [t[2] for t in self.titles]) \
            + "\n\n" + bill_text
    haystack_index = ('bill_type', 'congress', 'number', 'sponsor', 'current_status', 'terms', 'introduced_date', 'current_status_date', 'committees', 'cosponsors')
    haystack_index_extra = (('proscore', 'Float'), ('sponsor_party', 'MultiValue'), ('usc_citations_uptree', 'MultiValue'))
    def get_terms_index_list(self):
        return set([t.id for t in self.terms.all()])
    def get_committees_index_list(self):
        return [c.id for c in self.committees.all()]
    def get_cosponsors_index_list(self):
        return [c.id for c in self.cosponsors.all()]
    def proscore(self):
        """A modified prognosis score that omits factors associated with uninteresting bills, such as naming post offices. Only truly valid for current bills, and useless to compare across Congresses, but returns a value for all bills."""
        # To aid search, especially for non-current bills, add in something to give most recently active bills a boost.
 
        type_boost = {
           BillType.senate_bill: 1.0, BillType.house_bill: 1.0,
           BillType.senate_resolution: 0.2, BillType.house_resolution: 0.2,
           BillType.senate_concurrent_resolution: 0.3, BillType.house_concurrent_resolution: 0.3,
           BillType.senate_joint_resolution: 0.75, BillType.house_joint_resolution: 0.75,
        }
        
        cstart, cend = get_congress_dates(self.congress)
        csd = self.current_status_date
        if hasattr(csd, 'date'): csd = csd.date()
        r = (csd - cstart).days / 365.0 # ranges from 0.0 to about 2.0.
        if self.is_current:
            from prognosis import compute_prognosis
            r += compute_prognosis(self, proscore=True)["prediction"]
        r *= type_boost[self.bill_type]
        return r
    def sponsor_party(self):
        if not self.sponsor_role: return None
        mp = getattr(Bill, "_majority_party", { })
        if self.congress not in mp:
            from prognosis import load_majority_party
            mp[self.congress] = load_majority_party(self.congress)
            Bill._majority_party = mp
        p = self.sponsor_role.party
        return (p, "Majority Party" if p == mp[self.congress][self.bill_type] else "Minority Party")
    def usc_citations_uptree(self):
        # Index the list of citation sections (including all higher levels of hierarchy)
        # using the USCSection object IDs.
        
        # Load citation information from GPO MODS file.
        try:
            metadata = load_bill_text(self, None, mods_only=True)
        except IOError:
            return []
        if "citations" not in metadata: return []
        
        # For each USC-type citation...
        ret = set()
        for cite in metadata["citations"]:
            # Load the object, if it exists, and go up the TOC hierarchy indexing at every level.
            if cite["type"] not in ("usc-section", "usc-chapter"): continue
            try:
                sec_obj = USCSection.objects.get(citation=cite["key"])
            except: # USCSection.DoesNotExist and MultipleObjectsReturned both possible
                continue
            while sec_obj:
                ret.add(sec_obj.id)
                sec_obj = sec_obj.parent_section
        return ret
        
    # api
    api_recurse_on = ("sponsor", "sponsor_role")
    api_recurse_on_single = ("committees", "cosponsors", "terms")
    api_additional_fields = {
        "link": lambda obj : "http://www.govtrack.us" + obj.get_absolute_url(),
        "display_number": "display_number_no_congress_number",
        "title_without_number": "title_no_number",
        "bill_resolution_type": "noun",
        "current_status_description": "current_status_description",
        "is_current": "is_current",
        "is_alive": "is_alive",
        "thomas_link": "thomas_link",
        "noun": "noun",
    }
    api_example_id = 76416
    api_example_list = { "sort": "-introduced_date" }
        
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
    def bill_type_name_short(self):
        return self.bill_type_name.replace(" of Representatives", "")
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
    def slip_law_number(self):
        if not self.sliplawnum: return None
        return ("Pub" if self.sliplawpubpriv == "PUB" else "Pvt") + (".L. %d-%d" % (self.congress, self.sliplawnum))

    @property
    def cosponsor_count(self):
        return self.cosponsor_records.filter(withdrawn=None).count()
    @property
    def cosponsor_records(self):
        return Cosponsor.objects.filter(bill=self).order_by('joined', 'person__lastname', 'person__firstname')
    @property
    def cosponsor_counts_by_party(self):
        counts = { }
        for p in self.cosponsor_records.filter(withdrawn=None).select_related("role").values_list("role__party", flat=True):
            counts[p] = counts.get(p, 0) + 1
        counts = sorted(list(counts.items()), key=lambda kv : -kv[1])
        return counts

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
        
    def get_approved_links(self):
        return self.links.filter(approved=True)

    def get_prognosis(self):
        if self.congress != settings.CURRENT_CONGRESS: return None
        import prognosis
        prog = prognosis.compute_prognosis(self)
        prog["congressdates"] = get_congress_dates(prog["congress"])
        return prog
        
    def get_formatted_summary(self):
        s = get_formatted_bill_summary(self)
        # this cleanup doesn't always work because sometimes the line is split between <divs>
        s = re.sub(r"(\d+/\d+/\d\d\d\d)--[^\.]+.\s*(\(This measure has not been amended since it was .*\. The summary of that version is repeated here\.\)\s*)?(" + "|".join(re.escape(t[2]) for t in self.titles) + r")\s*-\s*", lambda m : m.group(1) + ". ", s)
        return s

    def get_upcoming_meetings(self):
        return CommitteeMeeting.objects.filter(when__gt=datetime.datetime.now(), bills=self)

    def get_status_text(self, status, date) :
        status = BillStatus.by_value(status).xml_code
        date = date.strftime("%B %d, %Y").replace(" 0", " ")
        status = get_bill_status_string(self.is_current, status)       
        return status % (self.noun, date)
        
    @property
    def explanatory_text(self):
        if self.title_no_number.startswith("Providing for consideration of the bill "):
            return "This resolution sets the rules for debate for another bill, such as limiting who can submit an amendment and setting floor debate time."
        if self.title_no_number.startswith("An original "):
            return "An original bill is one which is drafted and approved by a committee before it is formally introduced in the House or Senate."
        return None

    def thomas_link(self):
        """Returns the URL for the bill page on http://thomas.loc.gov."""
        return "http://thomas.loc.gov/cgi-bin/bdquery/z?d%03d:%s%d:" \
            % (self.congress, self.bill_type_slug, self.number)

    def popvox_link(self):
        """Returns the URL for the bill page on POPVOX."""
        return "https://www.popvox.com/bills/us/%d/%s%d" \
            % (self.congress, self.bill_type_slug, self.number)
            
    def create_events(self):
        if self.congress < 112: return # not interested, creates too much useless data and slow to load
        from events.models import Feed, Event
        with Event.update(self) as E:
            # collect the feeds that we'll add major actions to
            bill_feed = Feed.BillFeed(self)
            index_feeds = [bill_feed]
            if self.sponsor != None:
                index_feeds.append(Feed.PersonSponsorshipFeed(self.sponsor))
            index_feeds.extend([Feed.IssueFeed(ix) for ix in self.terms.all()])
            index_feeds.extend([Feed.CommitteeBillsFeed(cx) for cx in self.committees.all()])
            index_feeds.extend([Feed.objects.get_or_create(feedname="usc:" + str(sec))[0] for sec in self.usc_citations_uptree()])
            
            # also index into feeds for any related bills and previous versions of this bill
            # that people may still be tracking
            for rb in self.get_related_bills():
                index_feeds.append(Feed.BillFeed(rb.related_bill))
            for b in self.find_reintroductions():
                index_feeds.append(Feed.BillFeed(b))
            
            # generate events for major actions
            E.add("state:" + str(BillStatus.introduced), self.introduced_date, index_feeds + [Feed.ActiveBillsFeed(), Feed.IntroducedBillsFeed()])
            common_feeds = [Feed.ActiveBillsFeed(), Feed.ActiveBillsExceptIntroductionsFeed()]
            enacted_feed = [Feed.EnactedBillsFeed()]
            for datestr, state, text in self.major_actions:
                date = eval(datestr)
                if state == BillStatus.introduced:
                    continue # already indexed
                if state == BillStatus.referred and (date.date() - self.introduced_date).days == 0:
                    continue # don't dup these events so close
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
                
            # generate an event for each new GPO text availability
            from glob import glob
            from billtext import bill_gpo_status_codes
            bt = BillType.by_value(self.bill_type).xml_code
            for st in bill_gpo_status_codes:
                textfn = "data/us/bills.text/%s/%s/%s%d%s.pdf" % (self.congress, bt, bt, self.number, st) # use pdf since we don't modify it once we download it, and hopefully we actually have a displayable format like HTML
                if os.path.exists(textfn):
                    textmodtime = datetime.datetime.fromtimestamp(os.path.getmtime(textfn))
                    E.add("text:" + st, textmodtime, index_feeds)
                    
            # generate an event for the main summary
            bs = BillSummary.objects.filter(bill=self)
            if len(bs) > 0:
                E.add("summary", bs[0].created, index_feeds + [Feed.from_name("misc:billsummaries")])
               
    
    def render_event(self, eventid, feeds):
        if eventid == "dhg":
            return self.render_event_dhg(feeds)
        if eventid == "sfs":
            return self.render_event_sfs(feeds)
        if eventid == "summary":
            return self.render_event_summary(feeds)
            
        ev_type, ev_code = eventid.split(":")
        if ev_type == "state":
            return self.render_event_state(ev_code, feeds)
        elif ev_type == "cosp":
            return self.render_event_cosp(ev_code, feeds)
        elif ev_type == "text":
            return self.render_event_text(ev_code, feeds)
        else:
            raise Exception()
          
    def render_event_state(self, ev_code, feeds):
        from status import BillStatus
        status = BillStatus.by_value(int(ev_code))
        date = self.introduced_date
        action = None
        action_type = None
        reps_on_committees = []
       
        if status == BillStatus.introduced:
            action_type = "introduced"
        else:
            for datestr, st, text in self.major_actions:
                if st == status:
                    date = eval(datestr)
                    action = text
                    break
            else:
                raise Exception("Invalid %s event in %s." % (status, str(self)))
        
        if self.is_current and BillStatus.by_value(status).xml_code == "INTRODUCED":
            cmtes = list(self.committees.all())
            if not cmtes:
                explanation = "This %s is in the first stage of the legislative process. It will typically be considered by committee next." % self.noun
            else:
                def nice_list(items, max_count):
                    if len(items) > max_count:
                        if len(items) == max_count+1:
                            items[max_count:] = ["one other committee"]
                        else:
                            items[max_count:] = [str(len(items)-max_count) + " other committees"]
                    if len(items) == 1:
                        return items[0]
                    elif len(items) == 2:
                        return items[0] + " and " + items[1]
                    else:
                        return ", ".join(items[0:-1]) + ", and " + items[-1]
                explanation = "This %s was referred to the %s which will consider it before sending it to the %s floor for consideration." % (
                    self.noun,
                    nice_list(sorted(c.fullname for c in cmtes), 2),
                    self.originating_chamber)
                
                # See if any tracked reps are members of the committees. Also
                # check the bill's sponsor, since we display it.
                reps_tracked = set()
                if self.sponsor: reps_tracked.add(self.sponsor)
                for f in feeds:
                    if f.feedname.split(":")[0] not in ("p", "ps", "pv"): continue
                    reps_tracked.add(f.person())
                mbrs = list(CommitteeMember.objects.filter(person__in=reps_tracked, committee__in=cmtes))
                if len(mbrs) > 0:
                    mbrs.sort(key = lambda m : (-MEMBER_ROLE_WEIGHTS[m.role], m.committee.shortname))
                    for m in mbrs:
                        reps_on_committees.append(m.person.name + " is " + m.role_name_2() + " the " + (m.committee.fullname if len(cmtes) > 1 else "committee") + ".")
                else:
                    # Neither the sponsor nor any tracked reps are on those committes.
                    # What about cosponsors?
                    m = CommitteeMember.objects.filter(person__in=self.cosponsors.all(), committee__in=cmtes).count()
                    if m > 0:
                        reps_on_committees.append("%d cosponsor%s on %s." % (
                            m,
                            " is" if m == 1 else "s are",
                            "that committee" if len(cmtes) == 1 else "those committees"))
                    
        else:
            explanation = self.get_status_text(status, date)


        return {
            "type": status.label,
            "date": date,
            "date_has_no_time": isinstance(date, datetime.date) or date.time() == datetime.time.min,
            "title": self.title,
            "url": self.get_absolute_url(),
            "body_text_template":
"""{% if sponsor and action_type == 'introduced' %}Sponsor: {{sponsor|safe}}{% endif %}
{% if action %}Last Action: {{action|safe}}{% endif %}
{% if action %}Explanation: {% endif %}{{summary|safe}}
{% for rep in reps_on_committees %}
{{rep}}{% endfor %}""",
            "body_html_template":
"""{% if sponsor and action_type == 'introduced' %}<p>Sponsor: <a href="{{SITE_ROOT}}{{sponsor.get_absolute_url}}">{{sponsor}}</a></p>{% endif %}
{% if action %}<p>Last Action: {{action}}</p>{% endif %}
<p>{% if action %}Explanation: {% endif %}{{summary}}</p>
{% for rep in reps_on_committees %}<p>{{rep}}</p>{% endfor %}
""",
            "context": {
                "sponsor": self.sponsor,
                "action": action,
                "action_type": action_type,
                "summary": explanation,
                "reps_on_committees": reps_on_committees,
                }
            }

    def render_event_cosp(self, ev_code, feeds):
        cosp = Cosponsor.objects.filter(bill=self, withdrawn=None, joined=ev_code)
        if len(cosp) == 0:
            # What to do if there are no longer new cosponsors on this date?
            # TODO test this.
            return {
                "type": "New Cosponsors",
                "date": datetime.date(*[int(k) for k in ev_code.split('-')]),
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
"""{% for p in cosponsors %}New Cosponsor: {{ p.person.name }}
{% endfor %}""",
            "body_html_template": """{% for p in cosponsors %}<p>New Cosponsor: <a href="{{SITE_ROOT}}{{p.person.get_absolute_url}}">{{ p.person.name }}</a></p>{% endfor %}""",
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
            "body_text_template": """This {{noun}} has been added to the House's schedule for the coming week, according to the House Majority Leader. More information can be found at http://docs.house.gov.\n\nLast Action: {{current_status}}""",
            "body_html_template": """<p>This {{noun}} has been added to the House&rsquo;s schedule for the coming week, according to the House Majority Leader. See <a href="http://docs.house.gov">the week ahead</a>.</p><p>Last Action: {{current_status}}</p>""",
            "context": { "noun": self.noun, "current_status": self.current_status_description },
            }
    def render_event_sfs(self, feeds):
        return {
            "type": "Legislation Coming Up",
            "date": self.senate_floor_schedule_postdate,
            "date_has_no_time": False,
            "title": self.title,
            "url": self.get_absolute_url(),
            "body_text_template": """This {{noun}} has been added to the Senate's floor schedule for the next legislative day.\n\nnLast Action: {{current_status}}""",
            "body_html_template": """<p>This {{noun}} has been added to the Senate&rsquo;s floor schedule for the next legislative day.</p><p>Last Action: {{current_status}}</p>""",
            "context": { "noun": self.noun, "current_status": self.current_status_description },
            }
        
    def render_event_text(self, ev_code, feeds):
        from billtext import bill_gpo_status_codes, load_bill_text
        if not ev_code in bill_gpo_status_codes: raise Exception()
        bt = BillType.by_value(self.bill_type).xml_code
        textfn = "data/us/bills.text/%s/%s/%s%d%s.pdf" % (self.congress, bt, bt, self.number, ev_code) # use pdf since we don't modify it once we download it, and hopefully we actually have a displayable format like HTML
        if not os.path.exists(textfn): raise Exception()
        
        try:
            modsinfo = load_bill_text(self, ev_code, mods_only=True)
        except IOError:
            modsinfo = { "docdate": "Unknown Date", "doc_version_name": "Unknown Version" }
        
        return {
            "type": "Bill Text",
            "date": datetime.datetime.fromtimestamp(os.path.getmtime(textfn)),
            "date_has_no_time": False,
            "title": self.title,
            "url": self.get_absolute_url() + "/text",
            "body_text_template": """This {{noun}}'s text {% if doc_version_name != "Introduced" %}for status <{{doc_version_name}}> ({{doc_date}}) {% endif %}is now available.""",
            "body_html_template": """<p>This {{noun}}&rsquo;s text {% if doc_version_name != "Introduced" %}for status <i>{{doc_version_name}}</i> ({{doc_date}}) {% endif %}is now available.</p>""",
            "context": { "noun": self.noun, "doc_date": modsinfo["docdate"], "doc_version_name": modsinfo["doc_version_name"] },
            }
        
    def render_event_summary(self, feeds):
        bs = self.oursummary
        return {
            "type": "Bill Summary",
            "date": bs.created,
            "date_has_no_time": False,
            "title": self.title,
            "url": self.get_absolute_url() + "#summary/oursummary",
            "body_text_template": """{{summary.plain_text|truncatewords:80}}""",
            "body_html_template": """{{summary.content|truncatewords_html:80|safe}}""",
            "context": { "summary": bs },
            }

    def get_major_events(self):
        if self.congress < 93: return []
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
        
        if self.docs_house_gov_postdate: ret.append({ "label": "On House Schedule", "date": self.docs_house_gov_postdate })
        if self.senate_floor_schedule_postdate: ret.append({ "label": "On Senate Schedule", "date": self.senate_floor_schedule_postdate })
        def as_dt(x):
            if isinstance(x, datetime.datetime): return x
            return datetime.datetime.combine(x, datetime.time.min)
        ret.sort(key = lambda x : as_dt(x["date"])) # only needed because of the previous two
        
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
        
    def get_top_term(self):
        try:
            return [t for t in self.terms.all() if t.is_top_term()][0]
        except IndexError:
            return None
    def get_top_term_id(self):
        t = self.get_top_term()
        if t: t = t.id
        return t
        
    def get_terms_sorted(self):
        terms = list(self.terms.all())
        terms.sort(key = lambda x : (not x.is_top_term(), x.name))
        return terms
        
    def get_related_bills(self):
        # Gets a unqie list of related bills, sorted by the relation type, whether the titles are
        # the same, and the last action date.
        ret = []
        seen = set()
        bills = list(self.relatedbills.all().select_related("related_bill"))
        bills.sort(key = lambda rb : (
            -RelatedBill.relation_sort_order.get(rb.relation, 999),
            self.title_no_number==rb.related_bill.title_no_number,
            rb.related_bill.current_status_date
            ), reverse=True)
        for rb in bills:
            if not rb.related_bill in seen:
                ret.append(rb)
                seen.add(rb.related_bill)
        return ret
        
    def get_related_bills_newer(self):
        return [rb for rb in self.get_related_bills()
            if self.title_no_number == rb.related_bill.title_no_number 
            and rb.related_bill.current_status_date > self.current_status_date]

    def find_reintroductions(self):
        def normalize_title(title): # remove anything that looks like a year
            return re.sub(r"of \d\d\d\d$", "", title)
        for reintro in Bill.objects.exclude(congress=self.congress).filter(sponsor=self.sponsor).order_by('congress'):
            if normalize_title(self.title_no_number) != normalize_title(reintro.title_no_number): continue
            yield reintro

    
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
            
    def get_gop_summary(self):
        import urllib, StringIO
        try:
            from django.utils.safestring import mark_safe
            dom = etree.parse(urllib.urlopen("http://www.gop.gov/api/bills.get?congress=%d&number=%s%d" % (self.congress, BillType.by_value(self.bill_type).slug, self.number)))
        except:
            return None
        if dom.getroot().tag == '{http://www.w3.org/1999/xhtml}html': return None
        def sanitize(s, as_text=False):
            if s.strip() == "": return None
            return mark_safe("".join(
                etree.tostring(n, method="html" if not as_text else "text", encoding=unicode)
                for n
                in etree.parse(StringIO.StringIO(s), etree.HTMLParser(remove_comments=True, remove_pis=True)).xpath("body")[0]))
        ret = {
            "link": unicode(dom.xpath("string(bill/permalink)")),
            "summary": sanitize(dom.xpath("string(bill/analysis/bill-summary)")),
            "background": sanitize(dom.xpath("string(bill/analysis/background)")),
            "cost": sanitize(dom.xpath("string(bill/analysis/cost)")),
        }
        if ret["cost"] and "was not available as of press time" in ret["cost"]: ret["cost"] = None
        # floor-situation is also interesting but largely redundant with what we already know
        # take the first of background and bill-summary and make a text-only version
        for f in ("background", "bill-summary"):
            ret["text"] = sanitize(dom.xpath("string(bill/analysis/%s)" % f), as_text=True)
            if ret["text"]: break
        return ret
            
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
            <div style="margin-left: 2em" xml:space="preserve">  <!-- 'preserve' prevents a self-closing tag which breaks HTML parse -->
                <xsl:apply-templates/>
            </div>
            </xsl:otherwise>
            </xsl:choose>
        </div>
        </xsl:if>
    </xsl:template>
</xsl:stylesheet>''')
    transform = etree.XSLT(xslt_root)
    summary = unicode(transform(dom))
    if summary.strip() == "":
        return None
    return summary

class BillLink(models.Model):
    bill = models.ForeignKey(Bill, db_index=True, related_name="links", on_delete=models.PROTECT)
    url = models.CharField(max_length=256)
    title = models.CharField(max_length=256)
    created = models.DateTimeField(auto_now_add=True)
    approved = models.BooleanField(default=False)
    class Meta:
        unique_together = ( ('bill', 'url'), )
        ordering = ('-created',)
    @property
    def hostname(self):
        return urlparse.urlparse(self.url).hostname

class BillTextComparison(models.Model):
    bill1 = models.ForeignKey(Bill, related_name="comparisons1")
    ver1 = models.CharField(max_length=6)
    bill2 = models.ForeignKey(Bill, related_name="comparisons2")
    ver2 = models.CharField(max_length=6)
    data = JSONField()
    class Meta:
        unique_together = ( ('bill1', 'ver1', 'bill2', 'ver2'), )
    def compress(self):
        import bz2, base64
        self.data["left_text_bz2"] = base64.b64encode(bz2.compress(self.data["left_text"]))
        self.data["right_text_bz2"] = base64.b64encode(bz2.compress(self.data["right_text"]))
        del self.data["left_text"]
        del self.data["right_text"]
    def decompress(self):
        import bz2, base64
        self.data["left_text"] = bz2.decompress(base64.b64decode(self.data["left_text_bz2"]))
        self.data["right_text"] = bz2.decompress(base64.b64decode(self.data["right_text_bz2"]))

# Bill search tracker.
from events.models import Feed
def bill_search_feed_title(q):
    from search import bill_search_manager
    return "Bill Search - " + bill_search_manager().describe_qs(q)
def bill_search_feed_execute(q):
    from search import bill_search_manager
    from settings import CURRENT_CONGRESS
    
    bills = bill_search_manager().execute_qs(q, overrides={'congress': CURRENT_CONGRESS}).order_by("-current_status_date")[0:100] # we have to limit to make this reasonably fast
    
    def make_feed_name(bill):
        return "bill:" + BillType.by_value(bill.bill_type).xml_code + str(bill.congress) + "-" + str(bill.number)
    return Feed.objects.filter(feedname__in=[make_feed_name(bill) for bill in bills if bill != None]) # batch load
Feed.register_feed(
    "billsearch:",
    title = lambda feed : bill_search_feed_title(feed.feedname.split(":", 1)[1]),
    link = lambda feed : "/congress/bills/browse?" + feed.feedname.split(":", 1)[1],
    includes = lambda feed : bill_search_feed_execute(feed.feedname.split(":", 1)[1]),
    meta = True,
    category = "federal-bills",
    description = "Get updates for all bills matching the keyword search, including major activity, being scheduled for debate, new cosponsors, etc.",
    )

# Summaries
class BillSummary(models.Model):
    bill = models.OneToOneField(Bill, related_name="oursummary", on_delete=models.PROTECT)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    content = models.TextField(blank=True)
    
    def plain_text(self):
        import re
        content = re.sub("<br>|<li>", " \n ", self.content, re.I)
        
        from django.utils.html import strip_tags
        content = strip_tags(content)
        
        content = content.replace("&nbsp;", " ")
        
        return content

# USC Citations
class USCSection(models.Model):
    parent_section = models.ForeignKey('self', blank=True, null=True, db_index=True)
    citation = models.CharField(max_length=32, blank=True, null=True, db_index=True)
    level_type = models.CharField(max_length=10, choices=[('title', 'Title'), ('subtitle', 'Subtitle'), ('chapter', 'Chapter'), ('subchapter', 'Subchapter'), ('part', 'Part'), ('subpart', 'Subpart'), ('division', 'Division'), ('heading', 'Heading'), ('section', 'Section')])
    number = models.CharField(max_length=24, blank=True, null=True)
    deambig = models.IntegerField(default=0) # disambiguates two sections with the same parent, level_type, and number by their order in the source file
    name = models.TextField(blank=True, null=True)
    ordering = models.IntegerField()
    update_flag = models.IntegerField(default=0)
    
    def __unicode__(self):
        return ((unicode(self.parent_section) + " > ") if self.parent_section else "") + self.get_level_type_display() + " "  + (self.number if self.number else "[No Number]")
    
    @property
    def name_recased(self):
        exceptions = ("and", "of", "the", "a", "an")
        if self.name and self.name == self.name.upper():
            return " ".join([w if i == 0 or w.lower() not in exceptions else w.lower() for i, w in enumerate(self.name.title().split(" "))])
        return self.name
    
    @property
    def citation_or_id(self):
        if self.citation:
            # check that it is unique
            try:
                USCSection.objects.get(citation=self.citation)
                return self.citation
            except:
                pass # pass through if there are multiple instances
        return self.id
        
    def get_absolute_url(self):
        return "/congress/bills/uscode/" + str(self.citation_or_id).replace("usc/", "")
    
    # utility methods to load from the structure.json file created by github:unitedstates/uscode
    # don't forget:
    #   * These objects are used in feeds. Delete with care.
    #     After loading, obsoleted entries are left with update_flag=0.
    #     Check if any of those are used in feeds before deleting them.
    #   * After loading, create a fixture to bootstrap local deployments of the website & backups.
    #     ./manage.py dumpdata --format json bill.USCSection > data/db/django-fixture-usc_sections.json
    @staticmethod
    def load_data_new():
        import json
        D = json.load(open("../../uscode/structure_xml.json"))
        D2 = json.load(open("../../uscode/structure_html.json"))
        for t in D2:
         if t["number"].endswith("a"):
          D.append(t)
        D.sort(key = lambda title : (int(title["number"].replace("a", "")), title["number"]))
        USCSection.load_data(D)
        print USCSection.objects.filter(update_flag=0).count(), "deleted sections" # .delete() ?
    @staticmethod
    def load_data(structure_data):
        if isinstance(structure_data, str):
            import json
            structure_data = json.load(open(structure_data))
        USCSection.objects.update(update_flag=0)
        USCSection.load_data2(None, structure_data)
    @staticmethod
    def load_data2(parent, sections):
        ambig = { }
        
        for i, sec in enumerate(sections):
            # because level/number may be ambiguous, count sequence too
            # this doesn't handle unnumbered headings very nicely, ah well
            deambig = ambig.get((sec["level"], sec.get("number")), 0)
            ambig[(sec["level"], sec.get("number"))] = deambig+1
            
            fields = {
                "name": sec.get("name"),
                "ordering": i,
                "citation": sec.get("citation"),
                "update_flag": 1,
            }
            
            ## Force a re-numbering on the deambig field.
            #for i2, s2 in enumerate(USCSection.objects.filter(
            #    parent_section=parent,
            #    level_type=sec["level"],
            #    number=sec.get("number")).order_by("ordering")[1:]):
            #    s2.deambig = i2+1
            #    s2.save()
            
            obj, is_new = USCSection.objects.get_or_create(
                parent_section=parent,
                level_type=sec["level"],
                number=sec.get("number"),
                deambig=deambig,
                defaults=fields)
            if not is_new:
                # update fields; importantly, set the update_flag
                for k, v in fields.items():
                    setattr(obj, k, v)
                obj.save()
            else:
                print "created", obj
            USCSection.load_data2(obj, sec.get("subparts", []))

Feed.register_feed(
    "usc:",
    title = lambda feed : unicode(USCSection.objects.get(id=feed.feedname.split(":", 1)[1])),
    link = lambda feed : USCSection.objects.get(id=feed.feedname.split(":", 1)[1]).get_absolute_url(),
    category = "federal-bills",
    description = "Get updates for bills citing this part of the U.S. Code, including major activity and when the bill is scheduled for debate.",
    )

Feed.register_feed(
    "misc:billsummaries",
    title = "GovTrack Bill Summaries",
    simple = True,
    slug = "bill-summaries",
    intro_html = """<p>This feed includes all GovTrack original research on legislation.</p>""",
    category = "federal-bills",
    description = "Get an update whenever we post a GovTrack original bill summary.",
    )

class AmendmentType(enum.Enum):
    senate_amendment = enum.Item(1, 'S.Amdt.', slug='s', full_name="Senate Amendment", search_help_text="Senate amendments")
    house_amendment = enum.Item(2, 'H.Amdt.', slug='h', full_name="House Amendment", search_help_text="House amendments")

class Amendment(models.Model):
    """An amendment to a bill."""

    congress = models.IntegerField(help_text="The number of the Congress in which the amendment was offered. The current Congress is %d." % settings.CURRENT_CONGRESS)
    amendment_type = models.IntegerField(choices=AmendmentType, help_text="The amendment's type, indicating the chmaber in which the amendment was offered.")
    number = models.IntegerField(help_text="The amendment's number according to the Library of Congress's H.Amdt and S.Amdt numbering (just the integer part).")
    bill = models.ForeignKey(Bill, help_text="The bill the amendment amends.")
    sequence = models.IntegerField(blank=True, null=True, help_text="For House amendments, the sequence number of the amendment (unique within a bill).")

    title = models.CharField(max_length=255, help_text="A title for the amendment.")

    sponsor = models.ForeignKey('person.Person', blank=True, null=True, related_name='sponsored_amendments', help_text="The sponsor of the amendment.", on_delete=models.PROTECT)
    sponsor_role = models.ForeignKey('person.PersonRole', blank=True, null=True, help_text="The role of the sponsor of the amendment at the time the amendment was offered.", on_delete=models.PROTECT)
    offered_date = models.DateField(help_text="The date the amendment was offered.")

    class Meta:
        unique_together = [('congress', 'amendment_type', 'number'),
            ('bill', 'sequence')]
            # bill+sequence is not unique, see the github thread on amendment numbering --- currently this is manually fixed up in the db as a non-unique index
        
    def __unicode__(self):
        return self.title


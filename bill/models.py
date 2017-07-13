# -*- coding: utf-8 -*-
from django.db import models
from django.template.defaultfilters import slugify, date as date_to_str
from django.core.urlresolvers import reverse

from common import enum
from jsonfield import JSONField

from committee.models import Committee, CommitteeMeeting, CommitteeMember, MEMBER_ROLE_WEIGHTS
from bill.status import BillStatus, get_bill_status_string
from bill.title import get_bill_number, get_primary_bill_title
from bill.billtext import load_bill_text, get_bill_text_versions, get_bill_text_metadata
from us import get_congress_dates, get_session_from_date

from django.conf import settings

import datetime, os.path, re, urlparse, markdown2
from lxml import etree

"Enums"

class BillType(enum.Enum):
    # slug must match regex for parse_bill_number
    senate_bill = enum.Item(2, 'S.', slug='s', xml_code='s', full_name="bill", search_help_text="Senate bills", chamber="Senate")
    house_bill = enum.Item(3, 'H.R.', slug='hr', xml_code='h', full_name="bill", search_help_text="House bills", chamber="House")
    senate_resolution = enum.Item(4, 'S.Res.', slug='sres', xml_code='sr', full_name="simple resolution", search_help_text="Senate simple resolutions, which do not have the force of law", chamber="Senate")
    house_resolution = enum.Item(1, 'H.Res.', slug='hres', xml_code='hr', full_name="simple resolution", search_help_text="House simple resolutions, which do not have the force of law", chamber="House")
    senate_concurrent_resolution = enum.Item(6, 'S.Con.Res.', slug='sconres', full_name="concurrent resolution", xml_code='sc', search_help_text="Concurrent resolutions originating in the Senate, which do not have the force of law", chamber="Senate")
    house_concurrent_resolution = enum.Item(5, 'H.Con.Res.', slug='hconres', full_name="concurrent resolution", xml_code='hc', search_help_text="Concurrent resolutions originating in the House, which do not have the force of law", chamber="House")
    senate_joint_resolution = enum.Item(8, 'S.J.Res.', slug='sjres', xml_code='sj', full_name="joint resolution", search_help_text="Joint resolutions originating in the Senate, which may be used to enact laws or propose constitutional amendments", chamber="Senate")
    house_joint_resolution = enum.Item(7, 'H.J.Res.', slug='hjres', xml_code='hj', full_name="joint resolution", search_help_text="Joint resolutions originating in the House, which may be used to enact laws or propose constitutional amendments", chamber="House")


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
        return "<BillTerm: %s:%s>" % (TermType.by_value(self.term_type).label, self.name.encode("utf8"))

    class Meta:
        unique_together = ('name', 'term_type')

    def is_top_term(self):
        return self.parents.count() == 0

    def get_absolute_url(self):
        return "/congress/bills/subjects/%s/%d" % (slugify(self.name).replace('-', '_'), self.id)

    def get_feed(self):
        from events.models import Feed
        return Feed.objects.get_or_create(feedname="crs:%d" % self.id)[0]

    @staticmethod
    def from_feed(feed, test=False):
        if not feed.feedname.startswith("crs:"): raise ValueError(feed.feedname)
        try:
           return BillTerm.objects.get(id=feed.feedname.split(":")[1])
        except BillTerm.DoesNotExist:
            if test: return False
            raise ValueError(feed.feedname)

           # For legacy calls to RSS feeds, try to map subject name to object.
           # Many subject names have changed, so this is the best we can do.
           # Only test against new-style subject terms since we don't generate
           # events for old bills with old subject terms.
           #try:
           #    return BillTerm.objects.get(name=feed.feedname.split(":")[1], term_type=TermType.new)
           #except BillTerm.DoesNotExist:
           #    raise ValueError(feed.feedname)

    @staticmethod
    def get_top_term_ids():
        from django.core.cache import cache
        key = "BillTerm.get_top_terms"
        ret = cache.get(key)
        if ret is not None: return ret
        ret = set([t.id for t in BillTerm.objects.filter(term_type=TermType.new) if t.is_top_term()])
        cache.set(key, ret, 60*60*24*7) # one week, cause this never changes
        return ret

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

    def __unicode__(self):
        return self.person_name + u" " + self.details() + u": " + unicode(self.bill)

    @property
    def person_name(self):
        # don't need title because it's implicit from the bill type
        from person.name import get_person_name
        self.person.role = self.role
        return get_person_name(self.person, firstname_position="after", show_title=False)

    def details(self):
        ret = []
        if self.joined: ret.append("joined " + date_to_str(self.joined))
        if self.withdrawn: ret.append("withdrawn " + date_to_str(self.withdrawn))
        if self.bill.is_current and not self.role.current: ret.append("no longer serving")
        return "; ".join(ret)

    @staticmethod
    def get_role_for(person, bill, joined_date):
        # TODO filter chamber in case person went between chambers same day?
        role = person.get_role_at_date(joined_date, congress=bill.congress)
        if role is not None: return role

        # Find closest.
        for role in person.roles.all():
            cn = role.congress_numbers()
            if cn is not None and bill.congress in cn:
                return role

        return None

    def is_valid(self):
        return self.role.startdate <= self.joined <= self.role.enddate and self.bill.congress in self.role.congress_numbers()

    @staticmethod
    def fixup_roles():
        # Sometimes the role column becomes incorrect if the PersonRole instance is updated
        # to new dates.

        # Fetch Cosponsor objects in chunks since we can't call .all() on the whole table.
        # Get all of the IDs first, then chunk the IDs, and fetch Cosponsor objects for each chunk.
        def fetch_in_chunks(qs, chunk_size):
            all_items = qs.values_list("id", flat=True)
            def make_iter(all_items):
                while all_items:
                    chunk = all_items[0:chunk_size]
                    all_items = all_items[len(chunk):]
                    for c in qs.in_bulk(chunk).values():
                        yield c
            return len(all_items), make_iter(list(all_items))

        # Iterate over all of the records. Check validity. Update where needed.
        import tqdm
        total, cosponsors = fetch_in_chunks(Cosponsor.objects.all().order_by('joined', 'person_id', 'bill_id').select_related("person", "role", "bill"), 2500)
        for c in tqdm.tqdm(cosponsors, total=total):
            if not c.role or not c.is_valid():
                new_role = Cosponsor.get_role_for(c.person, c.bill, c.joined)
                if new_role != c.role:
                    if new_role:
                        print c.person, c.joined, c.bill
                        print c.role, "=>", new_role
                        print
                        c.role = new_role
                        c.save()
                    else:
                        print c.person, c.joined, c.bill
                        print "can't update because no new role", c.role, "=> ?"
                        print

class Bill(models.Model):
    """A bill represents a bill or resolution introduced in the United States Congress."""

    title = models.CharField(max_length=255, help_text="The bill's primary display title, including its number.")
    lock_title = models.BooleanField(default=False, help_text="Whether the title has been manually overridden.")
    titles = JSONField(default=None) # serialized list of all bill titles as (type, as_of, text)
    bill_type = models.IntegerField(choices=BillType, help_text="The bill's type (e.g. H.R., S., H.J.Res. etc.)")
    congress = models.IntegerField(help_text="The number of the Congress in which the bill was introduced. The current Congress is %d." % settings.CURRENT_CONGRESS)
    number = models.IntegerField(help_text="The bill's number (just the integer part).")

    # primary data originally from USGPO bill status XML (or parallel source)
    sponsor = models.ForeignKey('person.Person', blank=True, null=True,
                                related_name='sponsored_bills', help_text="The primary sponsor of the bill.", on_delete=models.PROTECT)
    sponsor_role = models.ForeignKey('person.PersonRole', blank=True, null=True, help_text="The role of the primary sponsor of the bill at the time the bill was introduced.", on_delete=models.PROTECT)
    committees = models.ManyToManyField(Committee, related_name='bills', help_text="Committees to which the bill has been referred.")
    terms = models.ManyToManyField(BillTerm, related_name='bills', help_text="Subject areas associated with the bill.")
    current_status = models.IntegerField(choices=BillStatus, help_text="The current status of the bill.")
    current_status_date = models.DateField(help_text="The date of the last major action on the bill corresponding to the current_status.")
    introduced_date = models.DateField(help_text="The date the bill was introduced.")
    cosponsors = models.ManyToManyField('person.Person', blank=True, through='bill.Cosponsor', help_text="The bill's cosponsors.")
    major_actions = JSONField(default=[]) # serialized list of all major actions (date/datetime, BillStatus, description)
    committee_reports = JSONField(default=[], blank=True, null=True, help_text="serialized list of committee report citations")
    sliplawpubpriv = models.CharField(max_length=3, choices=[("PUB", "Public"), ("PRI", "Private")], blank=True, null=True, help_text="For enacted laws, whether the law is a public (PUB) or private (PRI) law. Unique with congress and sliplawnum.")
    sliplawnum = models.IntegerField(blank=True, null=True, help_text="For enacted laws, the slip law number (i.e. the law number in P.L. XXX-123). Unique with congress and sliplawpublpriv.")

    # what source actually produced the above information?
    source = models.CharField(max_length=16, choices=[("thomas-congproj", "THOMAS.gov (via Congress Project)"), ("statutesatlarge", "U.S. Statutes at Large"), ("americanmemory", "LoC American Memory Collection")], help_text="The primary source for this bill's metadata.")
    source_link = models.CharField(max_length=256, blank=True, null=True, help_text="When set, a link to the page on the primary source website for this bill. Set when source='americanmemory' only.")

    # additional data that is pulled from other sources
    docs_house_gov_postdate = models.DateTimeField(blank=True, null=True, help_text="The date on which the bill was posted to http://docs.house.gov (which is different from the date it was expected to be debated).")
    senate_floor_schedule_postdate = models.DateTimeField(blank=True, null=True, help_text="The date on which the bill was posted on the Senate Floor Schedule (which is different from the date it was expected to be debated).")
    scheduled_consideration_date = models.DateTimeField(blank=True, null=True, help_text="The date on which the bill is expected to be considered on the floor for the most recent of docs_house_gov_postdate and senate_floor_schedule_postdate, and if for docs.house.gov it is the week that this is the Monday of.")

    #statutescite = models.CharField(max_length=16, blank=True, null=True, help_text="For enacted laws, a normalized U.S. Statutes at Large citation. Available only for years in which the Statutes at Large has already been published.")
    text_incorporation = JSONField(default=[], blank=True, null=True, help_text="What enacted bills have provisions of this bill been incorporated into?")

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

    @staticmethod
    def from_congressproject_id(bill_id):
        m = re.match("^([a-z]+)(\d+)-(\d+)$", bill_id)
        if not m: raise ValueError("Invalid bill ID: " + bill_id)
        return Bill.objects.get(congress=int(m.group(3)), bill_type=BillType.by_slug(m.group(1)), number=int(m.group(2)))

    @property
    def congressproject_id(self):
        return self.bill_type_slug + str(self.number) + "-" + str(self.congress)

    @property
    def data_dir_path(self):
        return "data/congress/%d/bills/%s/%s%d" % (self.congress, BillType.by_value(self.bill_type).slug, BillType.by_value(self.bill_type).slug, self.number)

    #@models.permalink
    def get_absolute_url(self):
        return reverse('bill_details', args=(self.congress, BillType.by_value(self.bill_type).slug, self.number))

    # indexing
    def get_index_text(self):
        bill_text = load_bill_text(self, None, plain_text=True)
        if ((82 <= self.congress <= 92) or (103 <= self.congress)) and not bill_text: print "NO BILL TEXT", self
        summary_text = ""
        bs = BillSummary.objects.filter(bill=self).first()
        if bs: summary_text = bs.plain_text()
        return "\n".join([
            self.title,
            self.display_number_no_congress_number.replace(".", ""),
            self.display_number_no_congress_number.replace(".", "").replace(" ", ""),
            ] + [t[2] for t in self.titles]) \
            + "\n\n" + summary_text \
            + "\n\n" + bill_text
    def get_index_text_boosted(self):
        return self.title
    haystack_index = ('bill_type', 'congress', 'number', 'sponsor', 'current_status', 'terms', 'introduced_date', 'current_status_date', 'committees', 'cosponsors')
    haystack_index_extra = (('proscore', 'Float'), ('sponsor_party', 'MultiValue'), ('usc_citations_uptree', 'MultiValue'), ('enacted_ex', 'Boolean'))
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
    def enacted_ex(self):
        return self.was_enacted_ex() is not None
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
    def update_index(self, bill_index):
        # Update this bill in the search database.
        bill_index.update_object(self, using="bill")

    # api
    api_recurse_on = ("sponsor", "sponsor_role")
    api_recurse_on_single = ("committees", "cosponsors", "terms")
    api_additional_fields = {
        "link": lambda obj : settings.SITE_ROOT_URL + obj.get_absolute_url(),
        "display_number": "display_number_no_congress_number",
        "title_without_number": "title_no_number",
        "bill_resolution_type": "noun",
        "current_status_description": "current_status_description",
        "is_current": "is_current",
        "is_alive": "is_alive",
        "noun": "noun",
        "related_bills": "get_related_bills_api",
        "current_chamber": "current_chamber",
        "text_info": "get_text_info",
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
        if self.lock_title:
            return re.sub("^" + re.escape(self.display_number_no_congress_number+": "), "", self.title)
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
        # also see current_status_chamber
        return "House" if self.bill_type in (BillType.house_bill, BillType.house_resolution, BillType.house_joint_resolution, BillType.house_concurrent_resolution) else "Senate"
    @property
    def opposite_chamber(self):
        # also see current_status_chamber
        return "Senate" if self.bill_type in (BillType.house_bill, BillType.house_resolution, BillType.house_joint_resolution, BillType.house_concurrent_resolution) else "House"
    @property
    def current_chamber(self):
        status = BillStatus.by_value(self.current_status)
        if status in (BillStatus.introduced, BillStatus.reported):
            return self.originating_chamber.lower()
        elif hasattr(status, 'next_action_in'):
            return status.next_action_in
        else:
            # no pending action
            return None

    @property
    def how_a_bill_text(self):
        if self.bill_type in (BillType.senate_bill, BillType.house_bill):
            return "A bill must be passed by both the House and Senate in identical form and then be signed by the President to become law."
        elif self.bill_type in (BillType.senate_concurrent_resolution, BillType.house_concurrent_resolution):
            return "A concurrent resolution is often used for matters that affect the rules of Congress or to express the sentiment of Congress. It must be agreed to by both the House and Senate in identical form but is not signed by the President and does not carry the force of law."
        elif self.bill_type in (BillType.senate_joint_resolution, BillType.house_joint_resolution):
            return "A joint resolution is often used in the same manner as a bill. If passed by both the House and Senate in identical form and signed by the President, it becomes a law. Joint resolutions are also used to propose amendments to the Constitution."
        elif self.bill_type in (BillType.senate_resolution, BillType.house_resolution):
            return "A simple resolution is used for matters that affect just one chamber of Congress, often to change the rules of the chamber to set the manner of debate for a related bill. It must be agreed to in the chamber in which it was introduced. It is not voted on in the other chamber and does not have the force of law."
        raise ValueError()

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

    # STATUS STRINGS

    def get_current_status_display(self):
        # Override the default Django behavior.
        s = self.get_current_status_and_date()
        ret = s[0]
        if s[1]: ret += " (" + s[1] + ")"
        return ret

    def get_current_status_display_simple(self):
		# don't add any enacted-via-other-measures info
        s = self.get_current_status_and_date()
        return s[0]

    def get_current_status_and_date(self):
        status = BillStatus.by_value(self.current_status).label
        extended_status = None
        date = self.current_status_date
        if not self.is_final_status:
            if self.was_enacted_ex() is not None:
                extended_status = "Enacted Via Other Measures"
            elif self.text_incorporation: # not null, empty string, empty list
                extended_status = "Parts Incorporated Into Other Measures"
        return (status, extended_status, date)

    @property
    def current_status_description(self):
        """Descriptive text for the bill's current status."""
        if self.source == "americanmemory": return None # not known
        status = self.get_long_text_for_status(self.current_status, self.current_status_date)
        if not self.is_final_status:
            if self.was_enacted_ex() is not None:
                status += (" But provisions of this %s were incorporated into other %ss which were enacted" % (self.noun, self.noun)) \
                             + ((", so there will not likely be further activity on this %s" % self.noun) if self.is_current else "") + "."
            elif self.text_incorporation: # not null, empty string, empty list
                status += " Provisions of this %s were incorporated into other %ss." % (self.noun, self.noun)
        return status

    def get_long_text_for_status(self, status, date) :
        status = BillStatus.by_value(status).xml_code
        date = date.replace(year=2000).strftime("%B %d, YYYY").replace(" 0", " ").replace("YYYY", str(date.year)) # historical bills < 1900 would otherwise raise an error
        status = get_bill_status_string(self.is_current, status)
        return status % (self.noun, date)

    # STATUS FLAGS

    @property
    def is_current(self):
        """Whether the bill was introduced in the current session of Congress."""
        return self.congress == settings.CURRENT_CONGRESS
    @property
    def is_alive(self):
        """Whether the bill was introduced in the current session of Congress and the bill's status is not a final status (i.e. can take no more action like a failed vote)."""
        return self.congress == settings.CURRENT_CONGRESS and self.current_status not in BillStatus.final_status
    @property
    def is_final_status(self):
        """Whether the bill's current status is a final status."""
        return self.current_status in BillStatus.final_status
    def is_success(self):
        """Whether the bill was enacted (for bills) or passed (for resolutions)."""
        return self.current_status in BillStatus.final_status_passed
    @property
    def current_status_chamber(self):
        """Returns 'House', 'Senate', 'Unknown', or 'Done' indicating which chamber is currently considering the
        bill. 'Done' means the bill is dead or out of Congress."""
        if not self.is_alive or self.current_status in (BillStatus.passed_bill,):
            return 'Done'
        if self.current_status in (BillStatus.introduced, BillStatus.reported):
            return self.originating_chamber
        if self.current_status in (BillStatus.pass_over_house, BillStatus.pass_back_house, BillStatus.conference_passed_house, BillStatus.prov_kill_cloturefailed, BillStatus.override_pass_over_house):
            return "Senate"
        if self.current_status in (BillStatus.pass_over_senate, BillStatus.pass_back_senate, BillStatus.conference_passed_senate, BillStatus.prov_kill_suspensionfailed, BillStatus.override_pass_over_senate):
            return "House"
        return "Unknown" # prov_kill_pingpongfail, prov_kill_veto

    def get_approved_links(self):
        return self.links.filter(approved=True)

    def get_prognosis(self):
        if self.congress != settings.CURRENT_CONGRESS: return None
        # Load the predictgov prognosis data.
        from django.core.cache import cache
        key = "Bill.predictgov"
        ret = cache.get(key)
        if ret is None:
            try:
                import csv
                ret = { row["bill_id"].lower(): { "prediction": float(row["Prediction"])*100, "notes": row["descs"] }
                    for row in csv.DictReader(open("../scripts/predictgov/predictions.csv")) }
            except:
                # On any sort of error, just ignore.
                return None
            cache.set(key, ret, 60*60*4.5) # 4.5 hours, since the file is updated daily
        ret = ret.get(self.congressproject_id)
        if ret:
            ret["success_name"] = "enacted" if self.bill_type in (BillType.senate_bill, BillType.house_bill, BillType.senate_joint_resolution, BillType.house_joint_resolution) \
                else "agreed to"
        return ret

    def get_formatted_summary(self):
        return get_formatted_bill_summary(self)

    def has_text(self, status=None):
        try:
            modsinfo = load_bill_text(self, status)
            return True
        except IOError:
            return False

    def get_text_info(self, version=None, mods_only=True, with_citations=False):
        try:
            return load_bill_text(self, version, mods_only=mods_only, with_citations=with_citations)
        except IOError:
            return None

    def get_upcoming_meetings(self):
        return CommitteeMeeting.objects.filter(when__gt=datetime.datetime.now(), bills=self)

    @property
    def explanatory_text(self):
        if re.search("Appropriations? Act(( of| for Fiscal Year|,) \d\d\d\d)?$", self.title):
            return "The federal budget process occurs in two stages: appropriations and authorizations. This is an appropriations bill, which sets overall spending limits by agency or program. (Authorizations direct how federal funds should or should not be used.) Appropriations are typically made for single fiscal years (October 1 through September 30 of the next year)."
        if re.search("Authorizations? Act(( of| for Fiscal Year|,|, Fiscal Year) \d\d\d\d)?$", self.title):
            return "The federal budget process occurs in two stages: appropriations and authorizations. This is an authorization bill, which directs how federal funds should or should not be used. (It does not set overall spending limits, however, which are the subject of appropriations bills.) Authorizations are typically made for single fiscal years (October 1 through September 30 of the next year) but are often renewed in subsequent law."
        if re.search("(Reauthorization Act(( of| for Fiscal Year|,) \d\d\d\d)?$)|(^(A bill )?to (permanently )?reauthorize )", self.title_no_number, re.I):
            return "The federal budget process occurs in two stages: appropriations, which set overall spending limits by agency or program, and authorizations, which direct how federal funds should (or should not) be used. Appropriation and authorization provisions are typically made for single fiscal years. A reauthorization bill like this one renews the authorizations of an expiring law."
        if self.title_no_number.startswith("Providing for consideration of the "): # bill, joint resolution, etc.
            return "This resolution sets the rules for debate for another bill, such as limiting who can submit an amendment and setting floor debate time."
        if self.title_no_number.startswith("An original "):
            return "An \"original bill\" is one which is drafted and approved by a committee before it is formally introduced in the House or Senate."
        return None

    def loc_hdl_link(self):
        """Returns the Library of Congress Handle URL for the bill, e.g. http://hdl.loc.gov/loc.uscongress/legislation.114hr4330."""
        return "http://hdl.loc.gov/loc.uscongress/legislation.%d%s%d" \
            % (self.congress, self.bill_type_slug, self.number)

    def get_feed(self):
        from events.models import Feed
        bt = BillType.by_value(self.bill_type)
        return Feed.objects.get_or_create(feedname="bill:" + bt.xml_code + str(self.congress) + "-" + str(self.number))[0]

    @staticmethod
    def from_feed(feed):
        if not feed.feedname.startswith("bill:"): raise ValueError("Not a bill feed.")
        m = re.match(r"([a-z]+)(\d+)-(\d+)", feed.feedname.split(":")[1])
        bill_type = BillType.by_xml_code(m.group(1))
        return Bill.objects.get(congress=m.group(2), bill_type=bill_type, number=m.group(3))

    @staticmethod
    def ActiveBillsFeed():
        from events.models import Feed
        return Feed.get_noarg_feed("misc:activebills")
    
    @staticmethod
    def EnactedBillsFeed():
        from events.models import Feed
        return Feed.get_noarg_feed("misc:enactedbills")
    
    @staticmethod
    def IntroducedBillsFeed():
        from events.models import Feed
        return Feed.get_noarg_feed("misc:introducedbills")
    
    @staticmethod
    def ActiveBillsExceptIntroductionsFeed():
        from events.models import Feed
        return Feed.get_noarg_feed("misc:activebills2")
    
    @staticmethod
    def ComingUpFeed():
        from events.models import Feed
        return Feed.get_noarg_feed("misc:comingup")
    
    def create_events(self):
        if self.congress < 112: return # not interested, creates too much useless data and slow to load
        from events.models import Feed, Event
        with Event.update(self) as E:
            # collect the feeds that we'll add major actions to
            bill_feed = self.get_feed()
            index_feeds = [bill_feed]
            if self.sponsor != None:
                index_feeds.append(self.sponsor.get_feed("ps"))
            index_feeds.extend([ix.get_feed() for ix in self.terms.all()])
            index_feeds.extend([cx.get_feed("bills") for cx in self.committees.all()])
            index_feeds.extend([Feed.objects.get_or_create(feedname="usc:" + str(sec))[0] for sec in self.usc_citations_uptree()])

            # also index into feeds for any related bills and previous versions of this bill
            # that people may still be tracking. exclude related bills that are related to
            # lots of other bills --- e.g. appropriations bills are the chrismas tree that
            # many dozens of other bills are attached to, but when tracking an approps bill
            # especially indirectly through a bill search users probably dont want to get
            # events on all of the bills related to what's in the approps bills
            for rb in self.get_related_bills():
                if rb.related_bill.relatedbills.count() <= 20:
                    index_feeds.append(rb.related_bill.get_feed())
            for b in self.find_reintroductions():
                index_feeds.append(b.get_feed())

            # generate events for major actions
            E.add("state:" + str(BillStatus.introduced), self.introduced_date, index_feeds + [Bill.ActiveBillsFeed(), Bill.IntroducedBillsFeed()])
            common_feeds = [Bill.ActiveBillsFeed(), Bill.ActiveBillsExceptIntroductionsFeed()]
            enacted_feed = [Bill.EnactedBillsFeed()]
            for datestr, state, text, srcxml in self.major_actions:
                date = eval(datestr)
                if state == BillStatus.introduced:
                    continue # already indexed
                E.add("state:" + str(state), date, index_feeds + common_feeds + (enacted_feed if state in BillStatus.final_status_enacted_bill else []))

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
                E.add("dhg", self.docs_house_gov_postdate, index_feeds + common_feeds + [Bill.ComingUpFeed()])
            if self.senate_floor_schedule_postdate:
                E.add("sfs", self.senate_floor_schedule_postdate, index_feeds + common_feeds + [Bill.ComingUpFeed()])

            # generate an event for each new GPO text availability
            for st in get_bill_text_versions(self):
                E.add("text:" + st, get_bill_text_metadata(self, st)['issued_on'], index_feeds)

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

    @staticmethod
    def get_tracked_people(feeds):
        reps_tracked = set()
        from person.models import Person
        for f in (feeds if feeds else []):
            try:
                reps_tracked.add(Person.from_feed(f))
            except ValueError:
                pass # not a person-related feed
        return reps_tracked

    def render_event_state(self, ev_code, feeds):
        from status import BillStatus
        status = BillStatus.by_value(int(ev_code))
        date = self.introduced_date
        action = None
        action_type = None
        reps_on_committees = []
        reps_tracked = Bill.get_tracked_people(feeds)

        if status == BillStatus.introduced:
            action_type = "introduced"
        else:
            for datestr, st, text, srcxml in self.major_actions:
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
                reps_check_if_on_cmte = set()
                if self.sponsor: reps_check_if_on_cmte.add(self.sponsor)
                reps_check_if_on_cmte |= reps_tracked
                mbrs = list(CommitteeMember.objects.filter(person__in=reps_check_if_on_cmte, committee__in=cmtes))
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
            explanation = self.get_long_text_for_status(status, date)

        return {
            "type": status.label,
            "date": date,
            "date_has_no_time": isinstance(date, datetime.date) or date.time() == datetime.time.min,
            "title": self.title,
            "url": self.get_absolute_url(),
            "body_text_template":
"""{% if sponsor and show_sponsor %}Sponsor: {{sponsor|safe}}{% endif %}
{% if action %}Last Action: {{action|safe}}{% endif %}
{% if action %}Explanation: {% endif %}{{summary|safe}}
{% for rep in reps_on_committees %}
{{rep}}{% endfor %}""",
            "body_html_template":
"""{% if sponsor and show_sponsor %}<p>Sponsor: <a href="{{SITE_ROOT}}{{sponsor.get_absolute_url}}">{{sponsor}}</a></p>{% endif %}
{% if action %}<p>Last Action: {{action}}</p>{% endif %}
<p>{% if action %}Explanation: {% endif %}{{summary}}</p>
{% for rep in reps_on_committees %}<p>{{rep}}</p>{% endfor %}
""",
            "context": {
                "sponsor": self.sponsor,
                "action": action,
                "show_sponsor": action_type == 'introduced' or self.sponsor in reps_tracked,
                "summary": explanation,
                "reps_on_committees": reps_on_committees,
                }
            }

    def render_event_cosp(self, ev_code, feeds):
        cosp = Cosponsor.objects.filter(bill=self, withdrawn=None, joined=ev_code)
        cumulative_cosp = Cosponsor.objects.filter(bill=self, withdrawn=None, joined__lte=ev_code)
        cumulative_cosp_count = cumulative_cosp.count()
        cumulative_cosp_by_party = cumulative_cosp.values("role__party").annotate(count=models.Count('id'))
        cumulative_cosp_by_party = sorted(list(cumulative_cosp_by_party), key=lambda x : -x['count'])
        cumulative_cosp_by_party = ", ".join(("%d %s%s" % (x['count'], x['role__party'], "" if x['count'] == 1 else "s") for x in cumulative_cosp_by_party))

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
            "body_text_template": """{% for p in cosponsors %}New Cosponsor: {{ p.person.name }}
{% endfor %}
The {{noun}} now has {{cumulative_cosp_count}} cosponsor{{cumulative_cosp_count|pluralize}} ({{cumulative_cosp_by_party}}).
{% if sponsor and show_sponsor %}{{sponsor|safe}} is the sponsor of this {{noun}}.{% endif %}""",
            "body_html_template": """{% for p in cosponsors %}<p>New Cosponsor: <a href="{{SITE_ROOT}}{{p.person.get_absolute_url}}">{{ p.person.name }}</a></p>{% endfor %}
<p>The {{noun}} now has {{cumulative_cosp_count}} cosponsor{{cumulative_cosp_count|pluralize}} ({{cumulative_cosp_by_party}}).</p>
{% if sponsor and show_sponsor %}<p><a href="{{SITE_ROOT}}{{sponsor.get_absolute_url}}">{{sponsor}}</a> is the sponsor of this {{noun}}.</p>{% endif %}""",
            "context": {
                "cosponsors": cosp,
                "sponsor": self.sponsor,
                "show_sponsor": self.sponsor in Bill.get_tracked_people(feeds),
                "noun": self.noun,
                "cumulative_cosp_count": cumulative_cosp_count,
				"cumulative_cosp_by_party": cumulative_cosp_by_party,
                }
            }

    def render_event_dhg(self, feeds):
        return {
            "type": "Legislation Coming Up",
            "date": self.docs_house_gov_postdate,
            "date_has_no_time": False,
            "title": self.title,
            "url": self.get_absolute_url(),
            "body_text_template": """This {{noun}} has been added to the House's schedule for the coming week, according to the House Majority Leader. More information can be found at http://docs.house.gov/floor.\n\nLast Action: {{current_status}}""",
            "body_html_template": """<p>This {{noun}} has been added to the House&rsquo;s schedule for the coming week, according to the House Majority Leader. See <a href="http://docs.house.gov/floor/">the week ahead</a>.</p><p>Last Action: {{current_status}}</p>""",
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
        try:
            modsinfo = load_bill_text(self, ev_code, mods_only=True)
        except IOError:
            modsinfo = { "docdate": "Unknown Date", "doc_version_name": "Unknown Version" }

        return {
            "type": "Bill Text",
            "date": modsinfo["docdate"],
            "date_has_no_time": True,
            "title": self.title,
            "url": self.get_absolute_url() + "/text",
            "body_text_template": """This {{noun}}'s text {% if doc_version_name != "Introduced" %}for status <{{doc_version_name}}> ({{doc_date}}) {% endif %}is now available.
{% if sponsor and show_sponsor %}{{sponsor|safe}} is the sponsor of this {{noun}}.{% endif %}
""",
            "body_html_template": """<p>This {{noun}}&rsquo;s text {% if doc_version_name != "Introduced" %}for status <i>{{doc_version_name}}</i> ({{doc_date}}) {% endif %}is now available.</p>
{% if sponsor and show_sponsor %}<p><a href="{{SITE_ROOT}}{{sponsor.get_absolute_url}}">{{sponsor}}</a> is the sponsor of this {{noun}}.</p>{% endif %}
""",
            "context": {
				"noun": self.noun, "doc_date": modsinfo["docdate"], "doc_version_name": modsinfo["doc_version_name"],
                "sponsor": self.sponsor,
                "show_sponsor": self.sponsor in Bill.get_tracked_people(feeds),
				},
            }

    def render_event_summary(self, feeds):
        bs = self.oursummary
        return {
            "type": "Bill Summary",
            "date": bs.created,
            "date_has_no_time": False,
            "title": self.title,
            "url": self.get_absolute_url() + "/summary",
            "body_text_template": """{{summary.plain_text|truncatewords:80}}""",
            "body_html_template": """{{summary.as_html|truncatewords_html:80|safe}}""",
            "context": { "summary": bs },
            }

    def get_major_events(self, top=True):
        if self.congress < 93: return []
        ret = []
        saw_intro = False
        for i, (datestr, st, text, srcxml) in enumerate(self.major_actions):
            date = eval(datestr)
            srcnode = etree.fromstring(srcxml) if srcxml else None

            st_key = BillStatus.by_value(st).key
            explanation = BillStatus.by_value(st).explanation
            if callable(explanation): explanation = explanation(self)

            if st in (BillStatus.passed_bill, BillStatus.passed_concurrentres, BillStatus.enacted_veto_override) and srcnode is not None and srcnode.get("where") in ("h", "s") and srcnode.get("type") in ("vote2", "pingpong", "conference", "override"):
                ch = {"h":"House","s":"Senate"}[srcnode.get("where")]
                # PASSED:BILL only occurs on the second chamber, so indicate both agreed to in text
                if srcnode.get("type") == "vote2":
                    st = ("Passed %s" % ch)
                elif srcnode.get("type") == "pingpong":
                    st = ("%s Agreed to Changes" % ch)
                elif srcnode.get("type") == "conference":
                    st = ("Conference Report Agreed to by %s" % ch)
                elif srcnode.get("type") == "override":
                    st = ("%s Overrides Veto" % ch)
            else:
                if st == BillStatus.introduced: saw_intro = True
                st = BillStatus.by_value(st)
                try:
                    st = st.simple_label
                except:
                    st = st.label

            vote_text = None
            vote_obj = None
            if srcnode is not None and srcnode.get("where") in ("h", "s") and srcnode.get("type") in ("vote", "vote2", "pingpong", "conference", "override"):
                if srcnode.get("how") == "roll":
                    try:
                        from vote.models import Vote, CongressChamber, VoteSource
                        v = Vote.objects.get(congress=self.congress, session=get_session_from_date(date, congress=self.congress)[1],
	                        chamber=CongressChamber.senate if srcnode.get("where") == 's' else CongressChamber.house,
                            number=int(srcnode.get("roll")))
                        if v.source != VoteSource.keithpoole:
                            # The numbering of votes does not apply in the voteview data.
                            vote_obj = v
                    except Vote.DoesNotExist:
                        # Somehow the vote is missing.
                        pass
                else:
                    if srcnode.get("how") != "(method not recorded)":
                        vote_text = srcnode.get("how")

            ret.append({
                "key": st_key,
                "label": st,
                "date": date,
                "sort": (self, i),
                "actionline": text,
                "explanation": explanation,
                "vote_text": vote_text,
                "vote_obj": vote_obj,
            })
        if not saw_intro: ret.insert(0, { "key": BillStatus.introduced.key, "label": "Introduced", "date": self.introduced_date, "explanation": BillStatus.introduced.explanation })

        if top:
            # Was the bill scheduled for consideration?
            if self.docs_house_gov_postdate: ret.append({ "key": "schedule_house", "label": "On House Schedule", "date": self.docs_house_gov_postdate, "explanation": "The House indicated that this %s would be considered in the week ahead." % self.noun })
            if self.senate_floor_schedule_postdate: ret.append({ "key": "schedule_senate","label": "On Senate Schedule", "date": self.senate_floor_schedule_postdate, "explanation": "The Senate indicated that this %s would be considered in the days ahead." % self.noun })

            # Bring in text versions. Attach text information to an existing
            # corresponding status line if we have one, or otherwise add a new one.
            # Sanity check that the document date matches the date of the event
            # that we are attaching the text too. Enrolled bills may be printed
            # on a later date than the vote that caused the action, and since there's
            # only one enrolled action and one print, necessarily, we can skip
            # the date check there. Our "reported" status is when a bill is ordered
            # reported, and not actually reported, so the reported text also tends
            # to come much later but we still want to put it in the right place.
            # Just make sure it occurs chronologically between the event we want
            # to associate it with and the next major event listed for the bill.
            def as_date(dt): return dt.date() if isinstance(dt, datetime.datetime) else dt
            for st in get_bill_text_versions(self):
                m = get_bill_text_metadata(self, st)
                if m["version_code"] in ("rfs", "rfh", "rts", "rth", "rds", "rdh"): continue # 'referred' text is never interesting
                if m["version_code"] in ("pcs", "pch"): continue # calendaring status is never interesting
                for i, event in enumerate(ret):
                    if event["key"] in set(st.key for st in m["corresponding_status_codes"]) \
                        and (
                               (m['issued_on'] == as_date(event["date"])) # issued_on is always a date but the event date may be a datetime
                            or (m["version_code"] == "enr")
                            or (m["version_code"] in ("rs", "rh") and m['version_code'][-1] == self.originating_chamber[0].lower()
                                and m['issued_on'] >= as_date(event["date"])
                                and (i==len(ret)-1 or m['issued_on'] <= as_date(ret[i+1]["date"]) ))
                            ):
                        event["text_version"] = m['version_code']
                        if m['issued_on'] != as_date(event["date"]):
                            event["text_date"] = m['issued_on']
                        break
                else:
                    # Add a new entry.
                    ret.append({
                        "key": "text_version",
                        "label": "Text Published",
                        "explanation": "Updated bill text was published as of " + m["status_name"] + ".",
                        "date": m['issued_on'],
                        "text_version": m['version_code'],
                        "end_of_day": True,
                    })

            # Bring in committee meetings.
            for mtg in self.committeemeeting_set.all():
                ret.append({
                    "key": "reported",
                    "label": "Considered by " + unicode(mtg.committee),
                    "explanation": "A committee held a hearing or business meeting about the " + self.noun + ".",
                    "date": mtg.when,
                })


            # Bring in committee reports.
            for rpt in (self.committee_reports or []):
                # Parse the report citation.
                m = re.match(r"(S|H|Ex). Rept. (\d+)-(\d+)$", rpt)
                if not m:
                    continue
                report_type, report_congress, report_number = m.groups()
                report_type = report_type.lower() + "rpt"
                rpt_mods = "../scripts/congress-pdf-config/data/%s/crpt/%s/%s%s/mods.xml" % (report_congress, report_type, report_type, report_number)

                # Load the report's MODS metadata, if we have it.
                try:
                    import lxml.etree
                    rpt_mods = lxml.etree.parse(rpt_mods)
                    ns = { "mods": "http://www.loc.gov/mods/v3" }
                    docdate = rpt_mods.xpath("string(mods:originInfo/mods:dateIssued)", namespaces=ns)
                    docdate = datetime.date(*(int(d) for d in docdate.split("-")))
                    committee_name = \
                        { "H": "House", "S": "Senate" }[ rpt_mods.xpath("string(mods:extension/mods:congCommittee/@chamber)", namespaces=ns) ] \
                      + " " + rpt_mods.xpath("string(mods:extension/mods:congCommittee/mods:name[@type='authority-standard'])", namespaces=ns) # authority-short gives short committee name like Appropriations
                    gpo_pdf_url = rpt_mods.xpath("string(mods:location/mods:url[@displayLabel='PDF rendition'])", namespaces=ns)
                    numpages = rpt_mods.xpath("string(mods:physicalDescription/mods:extent)", namespaces=ns)
                    if numpages: numpages = re.sub(r" p\.$", " pages", numpages)
                except:
                    continue

                # Attach to an existing Reported event on the same date.
                # TODO: But this could be the wrong chamber if multiple reports on the same date? Probably
                # should check that the chamber matches the bill's originating chamber.
                for i, event in enumerate(ret):
                    if event["key"] == "reported" \
                       and docdate == as_date(event["date"]) \
                       and "committee_report_link" not in event:
                        event["explanation"] += " The %s issued the report which may provide insight into the purpose of the legislation." % committee_name
                        event["committee_report_link"] = gpo_pdf_url
                        break
                else:
                    # Add a new event.
                    ret.append({
                        "key": "committee_report",
                        "label": "Reported by " + committee_name,
                        "explanation": "A committee issued a report on the bill, which often provides helpful explanatory background on the issue addressed by the bill and the bill's intentions.",
                        "date": docdate,
                        "end_of_day": True,
                        "committee_report_link": gpo_pdf_url,
                    })

            # Bring in major events from bills with textual similarity.
            got_rb = set()
            if self.text_incorporation:
                for rec in self.text_incorporation:
                    b = Bill.from_congressproject_id(rec["other"])
                    got_rb.add(b)
                    for e in b.get_major_events(top=False):
                        if e["key"] in ("introduced", "reported"): continue
                        if rec["my_ratio"] * rec["other_ratio"] > .9:
                            e["relation"] = "Identical Bill"
                        elif self.is_success() and not b.is_success():
                            e["relation"] = "Source Bill"
                        elif not self.is_success() and b.is_success() and rec["my_ratio"] > .66:
                            e["relation"] = "Final Bill"
                        else:
                            e["relation"] = "Related Bill"
                        e["bill"] = b
                        ret.append(e)

            # Bring in major events from related bills identified by CRS,
            # except those we identified above and check for duplicates
            # here because pairs of bills may have multiple records.
            for relation_name, relation_types in (
              ("Companion Bill", ("identical",)),
              ("Alternative Bill", ("supersedes", "includes")),
              ("Bill Causing Indirect Action", ("caused-action",)),
              ("Rules Change", ("rule",))):
                for rb in self.relatedbills.filter(relation__in=relation_types).select_related("related_bill"):
                    if rb.related_bill in got_rb: continue
                    got_rb.add(rb.related_bill)
                    for e in rb.related_bill.get_major_events(top=False):
                        if e["key"] in ("introduced", "reported"): continue
                        e["relation"] = relation_name
                        e["bill"] = rb.related_bill
                        ret.append(e)

            # Bring in major events from earlier/later reintroductions of this bill.
            for b in self.find_reintroductions():
                be = b.get_major_events(top=False)
                if len(be) > 0:
                    e = be[-1] # just take the most recent major event
                    e["relation"] = "Earlier Version" if b.congress < self.congress else "Reintroduced Bill"
                    e["bill"] = b
                    e["different_congress"] = True
                    ret.append(e)

        # Sort the entries by date. Stable sort for time-less dates.
        # Put time-less dates before timed dates, except bill text.
        def as_dt(x, end_of_day=False):
            if isinstance(x, datetime.datetime): return x
            return datetime.datetime.combine(x, datetime.time.min if not end_of_day else datetime.time.max)
        def event_cmp(a, b):
            if a.get("sort") and b.get("sort") and a["sort"][0] == b["sort"][0]:
                return cmp(a["sort"], b["sort"])
            da = as_dt(a["date"], a.get("end_of_day", False))
            db = as_dt(b["date"], b.get("end_of_day", False))
            return cmp(da, db)
        ret.sort(cmp=event_cmp)

        if top:
            # Mark the last entry that occurs prior to all events on this bill.
            for i, event in enumerate(ret):
                if not event.get("bill"):
                    if i > 0:
                        ret[i-1]["last_preceding_activity"] = True
                    break

            # Create text comparison links.
            prev_text = None
            for event in ret:
                if event.get("text_version"):
                    if prev_text:
                        event["text_version_compare_to"] = prev_text
                    prev_text = event["text_version"]

        # Don't add future events when we're looking at related bills to the bill we really care about.
        if self.is_alive and top and not self.enacted_ex():
            if len(ret) > 0: # mark the last one differently for display purposes
                ret[-1]["last_occurred"] = True
            for key, label in self.get_future_events():
                ret.append({ "key": key, "label": label })

        return ret

    def get_future_events(self):
        # predict the major actions not yet occurred on the bill, based on its
        # current status.

        # define a state diagram
        common_paths = {
            BillStatus.introduced: BillStatus.reported,
        }

        type_specific_paths = {
            BillType.house_bill: {
                BillStatus.reported: BillStatus.pass_over_house,
                BillStatus.pass_over_house: (BillStatus.passed_bill, "Passed Senate"),
                BillStatus.pass_back_house: (BillStatus.passed_bill, "Senate Approves House Changes"),
                BillStatus.pass_back_senate: (BillStatus.passed_bill, "House Approves Senate Changes"),
                BillStatus.conference_passed_house: (BillStatus.passed_bill, "Conference Report Agreed to by Senate"),
                BillStatus.conference_passed_senate: (BillStatus.passed_bill, "Conference Report Agreed to by House"),
                BillStatus.passed_bill: (BillStatus.enacted_signed, "Signed by the President"),
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
                BillStatus.conference_passed_house: (BillStatus.passed_bill, "Conference Report Agreed to by Senate"),
                BillStatus.conference_passed_senate: (BillStatus.passed_bill, "Conference Report Agreed to by House"),
                BillStatus.passed_bill: (BillStatus.enacted_signed, "Signed by the President"),
                BillStatus.prov_kill_suspensionfailed: (BillStatus.passed_bill, "Passed House"),
                BillStatus.prov_kill_cloturefailed: BillStatus.pass_over_senate,
                BillStatus.prov_kill_pingpongfail: (BillStatus.passed_bill, "Passed Senate/House"),
                BillStatus.prov_kill_veto: BillStatus.override_pass_over_senate,
                BillStatus.override_pass_over_senate: BillStatus.enacted_veto_override,
            },
            BillType.house_resolution:  {
                BillStatus.reported: BillStatus.passed_simpleres,
                BillStatus.prov_kill_suspensionfailed: BillStatus.passed_simpleres,
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
                BillStatus.conference_passed_house: (BillStatus.passed_concurrentres, "Conference Report Agreed to by Senate"),
                BillStatus.conference_passed_senate: (BillStatus.passed_concurrentres, "Conference Report Agreed to by House"),
                BillStatus.prov_kill_suspensionfailed: BillStatus.pass_over_house,
                BillStatus.prov_kill_cloturefailed: BillStatus.passed_concurrentres,
                BillStatus.prov_kill_pingpongfail: BillStatus.passed_concurrentres,
            },
            BillType.senate_concurrent_resolution: {
                BillStatus.reported: BillStatus.pass_over_senate,
                BillStatus.pass_over_senate: (BillStatus.passed_concurrentres, "Passed House"),
                BillStatus.pass_back_house: (BillStatus.passed_concurrentres, "Senate Approves House Changes"),
                BillStatus.pass_back_senate: (BillStatus.passed_concurrentres, "House Approves Senate Changes"),
                BillStatus.conference_passed_house: (BillStatus.passed_concurrentres, "Conference Report Agreed to by Senate"),
                BillStatus.conference_passed_senate: (BillStatus.passed_concurrentres, "Conference Report Agreed to by House"),
                BillStatus.prov_kill_suspensionfailed: BillStatus.passed_concurrentres,
                BillStatus.prov_kill_cloturefailed: BillStatus.pass_over_senate,
                BillStatus.prov_kill_pingpongfail: BillStatus.passed_concurrentres,
            },
            BillType.house_joint_resolution: { # assuming const amend
                BillStatus.reported: BillStatus.pass_over_house,
                BillStatus.pass_over_house: (BillStatus.passed_constamend, "Passed Senate"),
                BillStatus.pass_back_house: BillStatus.passed_constamend,
                BillStatus.pass_back_senate: BillStatus.passed_constamend,
                BillStatus.conference_passed_house: BillStatus.passed_constamend,
                BillStatus.conference_passed_senate: BillStatus.passed_constamend,
                BillStatus.prov_kill_suspensionfailed: BillStatus.pass_over_house,
                BillStatus.prov_kill_cloturefailed: BillStatus.passed_constamend,
                BillStatus.prov_kill_pingpongfail: BillStatus.passed_constamend,
                BillStatus.passed_constamend: (None, "Ratified by State Legislatures"),
            },
            BillType.senate_joint_resolution: { # assuming const amend
                BillStatus.reported: BillStatus.pass_over_senate,
                BillStatus.pass_over_senate: (BillStatus.passed_constamend, "Passed House"),
                BillStatus.pass_back_house: BillStatus.passed_constamend,
                BillStatus.pass_back_senate: BillStatus.passed_constamend,
                BillStatus.conference_passed_house: BillStatus.passed_constamend,
                BillStatus.conference_passed_senate: BillStatus.passed_constamend,
                BillStatus.prov_kill_suspensionfailed: BillStatus.passed_constamend,
                BillStatus.prov_kill_cloturefailed: BillStatus.pass_over_senate,
                BillStatus.prov_kill_pingpongfail: BillStatus.passed_constamend,
                BillStatus.passed_constamend: (None, "Ratified by State Legislatures"),
            }
        }

        bt = self.bill_type
        if bt == BillType.house_joint_resolution and not "proposing an amendment" in self.title.lower(): bt = BillType.house_bill
        if bt == BillType.senate_joint_resolution and not "proposing an amendment" in self.title.lower(): bt = BillType.senate_bill

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
                try:
                    label = st.simple_label
                except:
                    label = st.label
            seq.append((st.key if st is not None else "status-unknown", label))

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

    def get_related_bills_api(self):
        return [ { "relation": rb.relation, "bill": rb.related_bill_id } for rb in self.get_related_bills() ]

    def get_related_bills_newer(self):
        return [rb for rb in self.get_related_bills()
            if self.title_no_number == rb.related_bill.title_no_number
            and rb.related_bill.current_status != BillStatus.introduced
            and rb.related_bill.current_status_date > self.current_status_date]

    def find_reintroductions(self):
        if self.sponsor == None: return
        def normalize_title(title): # remove anything that looks like a year
            return re.sub(r"of \d\d\d\d$", "", title)
        for reintro in Bill.objects.exclude(congress=self.congress).filter(sponsor=self.sponsor).order_by('congress'):
            if normalize_title(self.title_no_number) != normalize_title(reintro.title_no_number): continue
            yield reintro

    def was_enacted_ex(self, recurse=True, restrict_to_activity_in_date_range=None):
        # Checking if a bill was "enacted" in a popular sense is a little tricky.
        # A bill is enacted if it was signed by the president, etc.
        # And if a bill's provisions were substantially incorporated into a bill
        # that was enacted, then we can also say yes the original bill was enacted to.
        # The sponsor "gets credit", in some sense, for enacting a law.
        #
        # Although CRS identifies "identicial" bills, and if this bill is identical
        # to an enacted bill we might say this bill was enacted, in practice our
        # text_incorporation data is probably more correct because it looks at the
        # *most recent* text for a bill, while a CRS "identical bill" relation is
        # set if two bills were identical at either point in either's history.
        #
        # A bill may have provisions incorporated into multiple enacted bills.
        # We'll say that this bill was enacted if at least one third of its text
        # is found within enacted bills, across all of the text relations.
        #
        # We don't have text incoproration data for bills without XML text, which
        # began gradually around the 109th/110th Congress, so we also look at CRS
        # relations to fill in historical bills.
        #
        # Returns a list of bills that this bill was enacted via, including this
        # bill itself, or None if the bill was not "enacted".
        #
        # Some of our statistics wants to know if a bill was enacted within a certain
        # time frame, so there is that restriction too.

        def date_filter(d):
            if restrict_to_activity_in_date_range is None: return True
            return restrict_to_activity_in_date_range[0] <= d <= restrict_to_activity_in_date_range[1]

        # If we know the bill to have been enacted itself...
        if self.current_status in BillStatus.final_status_enacted_bill and date_filter(self.current_status_date.isoformat()):
            return [self]

        # Check related bills identified by text incorporation...
        if recurse and self.text_incorporation is not None:
            ret = []
            total_incorporated_ratio = 0
            for rec in self.text_incorporation:
                if rec["other_version"] == "enr":
                    # Enrolled, but enacted?
                    other_bill = Bill.from_congressproject_id(rec["other"])
                    if other_bill.was_enacted_ex(recurse=False, restrict_to_activity_in_date_range=restrict_to_activity_in_date_range):
                        ret.append(other_bill)
                        total_incorporated_ratio += rec["my_ratio"]
            if total_incorporated_ratio >= .33:
                return ret

        # Check identical bills identified by CRS, i.e. "companion" bills.
        if recurse:
            for rb in RelatedBill.objects.filter(bill=self, relation="identical").select_related("related_bill"):
                e = rb.related_bill.was_enacted_ex(recurse=False, restrict_to_activity_in_date_range=restrict_to_activity_in_date_range)
                if e is not None:
                     return [e]
               
        return None

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
    # Ok so we used to run a Perl script that took the plain text summary and
    # used regex to add XML structure, which we saved in a bills.summary directory.
    # Now we just read the original text scraped from THOMAS and split into paragraphs.

    # The file location for American Memory bills is in data/congress, and those don't
    # have summaries anyway.
    if bill.congress <= 42: return None

    import cgi
    sfn = "data/us/%d/bills/%s%d.xml" % (bill.congress, BillType.by_value(bill.bill_type).xml_code, bill.number)
    with open(sfn) as f:
       dom = etree.parse(f)

    summary = dom.find("summary")
    if summary is None: return None

    import dateutil.parser
    date = dateutil.parser.parse(summary.get("date")) if summary.get("date") else None

    summary = summary.text
    if summary.strip() == "": return None
    summary = "".join(["<p>" + cgi.escape(p) + "</p>\n" for p in summary.split("\n\n")])

    return date, summary

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

# Feeds
from events.models import Feed, truncate_words
Feed.register_feed(
    "misc:enactedbills",
    category = "federal-bills",
    description = "You will be alerted every time a law is enacted.",
    title = "New Laws",
    simple = True,
    sort_order = 104,
    single_event_type = True,
    slug = "enacted-bills",
    )
Feed.register_feed(
    "misc:comingup",
    category = "federal-bills",
    description = "You will get updates when any bill is scheduled for debate in the week ahead by the House Majority Leader or in the day ahead according to the Senate Floor Schedule.",
    title = "Legislation Coming Up",
    simple = True,
    sort_order = 102,
    single_event_type = True,
    slug = "coming-up",
    )
Feed.register_feed(
    "misc:activebills2",
    category = "federal-bills",
    description = "Get an update when any bill is scheduled for debate or has major action such as a vote or being enacted.",
    title = "Major Legislative Activity",
    simple = True,
    sort_order = 100,
    slug = "major-bill-activity",
    )
Feed.register_feed(
    "misc:activebills",
    category = "federal-bills",
    description = "Get an update when any bill is introduced, scheduled for debate, or has major action such as a vote or being enacted.",
    title = "All Legislative Activity",
    simple = True,
    sort_order = 105,
    slug = "bill-activity",
    )
Feed.register_feed(
    "misc:introducedbills",
    category = "federal-bills",
    description = "Get an update whenever a new bill or resolution is introduced.",
    title = "New Bills and Resolutions",
    simple = True,
    sort_order = 106,
    single_event_type = True,
    slug = "introduced-bills",
    )
Feed.register_feed(
    "bill:",
    title = lambda feed : truncate_words(Bill.from_feed(feed).title, 24),
    noun = "bill",
    link = lambda feed: Bill.from_feed(feed).get_absolute_url(),
    category = "federal-bills",
    description = "You will get updates when this bill is scheduled for debate, has a major action such as a vote, or gets a new cosponsor, when a committee meeting is scheduled, when bill text becomes available or when we write a bill summary, plus similar events for related bills.",
    is_subscribable = lambda feed : Bill.from_feed(feed).is_alive,
    track_button_noun = lambda feed : "This Bill",
    )
Feed.register_feed(
    "crs:",
    title = lambda feed : BillTerm.from_feed(feed).name,
    noun = "subject area",
    link = lambda feed: BillTerm.from_feed(feed).get_absolute_url(),
    is_valid = lambda feed : BillTerm.from_feed(feed, test=True),
    category = "federal-bills",
    description = "You will get updates about major activity on bills in this subject area including notices of newly introduced bills, updates when a bill is scheduled for debate, has a major action such as a vote, or gets a new cosponsor, when bill text becomes available or when we write a bill summary.",
    )

# Bill search tracker.
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
    source_url = models.TextField(blank=True, null=True)
    source_text = models.CharField(max_length=64, blank=True, null=True, db_index=True)

    def __unicode__(self):
        return unicode(self.bill)[0:30] + " - " + self.plain_text()[0:60]

    def as_html(self):
        if self.id < 75 or self.source_text == "Wikipedia":
            return self.content
        else:
            return markdown2.markdown(self.content)

    def plain_text(self):
        import re

        if not (self.id < 75 or self.source_text == "Wikipedia"):
            # Now stored in markdown. Kill links.
            content = re.sub("\[(.*?)\]\(.*?\)", r"\1", self.content)
            return content

		# Used to be HTML.
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

    def get_cornell_lii_link(self, subsection=None):
        import re
        if self.level_type == "section":
            uscstring, title, sec = self.citation.split("/")
            return "http://www.law.cornell.edu/uscode/text/" + title + "/" + sec \
                + ( ("#" + "_".join(re.findall(r"\(([^)]+)\)", subsection))) if subsection else "")
        else:
            # path to level through possible subtitles, parts, etc.
            path = [self]
            so = self
            while so.parent_section:
                so = so.parent_section
                path.append(so)
            if not path[-1].citation: return None # not a section actually in the USC
            path.reverse()
            return "http://www.law.cornell.edu/uscode/text/" + "/".join(
                (((so.level_type + "-") if so.level_type not in ("title", None) else "") + so.number) if so.number else "?" for so in path)

    # utility methods to load from the structure.json file created by github:unitedstates/uscode
    # don't forget:
    #   * STOP: The upstream 'citation' key has changed: usc/chapter/x/y is now usc/title/x/chapter/y
    #           And intermediate levels are similar.
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
    senate_unprinted_amendment = enum.Item(3, 'S.Up.Amdt.', slug='sup', full_name="Senate Unprinted Amendment", search_help_text="Senate \"unprinted\" amendments")

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

    def display_number(self):
        from django.contrib.humanize.templatetags.humanize import ordinal
        ret = '%s %s' % (AmendmentType.by_value(self.amendment_type).label, self.number)
        if self.congress != settings.CURRENT_CONGRESS:
            ret += ' (%s)' % ordinal(self.congress)
        return ret

    def congressdotgov_link(self):
        return "https://www.congress.gov/amendment/%d/%s/%s" % (self.congress, AmendmentType.by_value(self.amendment_type).full_name.lower().replace(" ", "-"), self.number)

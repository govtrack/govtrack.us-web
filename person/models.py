# -*- coding: utf-8 -*-
from django.db import models
from django.template.defaultfilters import slugify
from django.conf import settings
from django.core.cache import cache

import datetime, json, os.path
from dateutil.relativedelta import relativedelta
from jsonfield import JSONField

from common import enum
from person.types import Gender, RoleType, SenatorClass, SenatorRank
from name import get_person_name

from us import stateapportionment, get_congress_dates, statenames, get_congress_from_date, get_all_sessions

import functools
def cache_result(f):
    @functools.wraps(f)
    def g(self):
        if hasattr(self, "role"): return f(self)
        ckey = "cache_result_%s_%s_%d" % (self.__class__.__name__, f.__name__, self.id)
        v = cache.get(ckey)
        if not v:
            v = f(self)
            cache.set(ckey, v)
        return v
    return g

class Person(models.Model):
    """Members of Congress, Presidents, and Vice Presidents since the founding of the nation."""
	
    firstname = models.CharField(max_length=255, help_text="The person's first name or first initial.")
    lastname = models.CharField(max_length=255, help_text="The person's last name.")
    middlename = models.CharField(max_length=255, blank=True, help_text="The person's middle name (optional).")

    # misc
    birthday = models.DateField(blank=True, null=True, help_text="The person's birthday.")
    gender = models.IntegerField(choices=Gender, blank=True, null=True, help_text="The person's gender, if known. For historical data, the gender is sometimes not known.")
    
    # namemod set(['II', 'Jr.', 'Sr.', 'III', 'IV'])
    namemod = models.CharField(max_length=10, blank=True, help_text="The suffix on the person's name usually one of Jr., Sr., I, II, etc.")
    nickname = models.CharField(max_length=255, blank=True, help_text="The person's nickname. If set, the nickname should usually be displayed in quotes where a middle name would go. For instance, Joe \"Buster\" Smith.")

    # links
    bioguideid = models.CharField(max_length=255, blank=True, null=True, help_text="The person's ID on bioguide.congress.gov. May be null if the person served only as a president and not in Congress.")
    pvsid = models.CharField(max_length=255, blank=True, null=True, help_text="The person's ID on vote-smart.org (Project Vote Smart), if known.")
    osid = models.CharField(max_length=255, blank=True, null=True, help_text="The person's ID on opensecrets.org (The Center for Responsive Politics), if known.")
    youtubeid = models.CharField(max_length=255, blank=True, null=True, help_text="The name of the person's official YouTube channel, if known.")
    twitterid = models.CharField(max_length=50, blank=True, null=True, help_text="The name of the person's official Twitter handle, if known.")
    cspanid = models.IntegerField(blank=True, null=True, help_text="The ID of the person on CSPAN websites, if known.")
    
    # cached name info
    name = models.CharField(max_length=96, help_text="The person's full name with title, district, and party information for current Members of Congress, in a typical display format.")
    sortname = models.CharField(max_length=64, help_text="The person's name suitable for sorting lexicographically by last name or for display in a sorted list of names. Title, district, and party information are included for current Members of Congress.")
    

    # indexing
    def get_index_text(self):
        # We need to index the name, and also the name without
        # hard-to-type characters.
        def str2(s): return s if s != None else ""
        import unicodedata
        n = self.name_no_details().replace(u"\u201c", " ").replace(u"\u201d", " ")
        r = n + "\n" + \
            u"".join(c for c in unicodedata.normalize('NFKD', n) if not unicodedata.combining(c)) + "\n"
        most_recent_role = self.get_most_recent_role()
        if most_recent_role:
            r += str2(most_recent_role.state) + " " + str2(statenames.get(most_recent_role.state))
        return r
    def get_index_text_boosted(self):
        return self.lastname
    haystack_index = ('sortname', 'gender')
    haystack_index_extra = (
        ('is_currently_serving', 'Boolean'),
        ('current_role_type', 'Integer'), ('current_role_title', 'Char'), ('all_role_types', 'MultiValue'),
        ('current_role_state', 'Char'), ('all_role_states', 'MultiValue'),
        ('current_role_district', 'Integer'), ('all_role_districts', 'MultiValue'),
        ('current_role_party', 'Char'), ('all_role_parties', 'MultiValue'),
        ('first_took_office', 'Date'), ('left_office', 'Date'))
    def get_current_role_field(self, fieldname):
        # Returns the value of a field on a current PersonRole for
        # this Person. If the Person has no current role, returns None.
        role = self.get_current_role()
        if not role: return None
        ret = getattr(role, fieldname)
        if callable(ret): ret = ret()
        return ret
    def current_role_type(self):
        return self.get_current_role_field('role_type')
    def current_role_title(self):
        return self.get_current_role_field('get_title')
    def all_role_types(self):
        return set(self.roles.values_list("role_type", flat=True))
    def current_role_state(self):
        return self.get_current_role_field('state')
    def all_role_states(self):
        return set(self.roles.values_list("state", flat=True))
    def current_role_district(self):
        return self.get_current_role_field('district')
    def all_role_districts(self):
        # combine the state and district so that filtering on
        # state=A district=X doesn't return a Person with values
        # [(state=A, district=Y), (state=B, district=X)].
        # Exclude districts that are empty (None, i.e. for senators
        # presidents, etc.) or unknown (-1).
        return set("%s-%02d" % sd for sd in self.roles.values_list("state", "district")
            if sd[1] not in (None, -1))
    def current_role_party(self):
        return self.get_current_role_field('party')
    def all_role_parties(self):
        return set(self.roles.values_list("party", flat=True))
    def first_took_office(self):
        # first took office for the most recent role
        role = self.get_most_recent_role()
        if not role: return None
        return role.logical_dates()[0]
    def left_office(self):
        # term end date for the most recent role
        role = self.get_most_recent_role()
        if not role: return None
        return role.enddate

    #######
    # api
    api_recurse_on_single = ('roles', 'committeeassignments')
    api_additional_fields = {
        "link": lambda obj : settings.SITE_ROOT_URL + obj.get_absolute_url(),
    }
    api_example_id = 400326
    #######

    def __unicode__(self):
        return self.name

    @staticmethod
    def from_state_and_district(state, district):
        qs = PersonRole.objects.filter(current=True).select_related("person")
        qs = qs.filter(role_type=RoleType.representative, state=state, district=district) \
            | qs.filter(role_type=RoleType.senator, state=state)
        ret = []
        for role in qs:
            person = role.person
            person.role = role
            ret.append(person)
        ret.sort(key = lambda person : (person.role.get_sort_key(), person.sortname))
        return ret

    @property
    def fullname(self):
        return u'%s %s' % (self.firstname, self.lastname)

    @cache_result
    def name_no_district(self):
        return get_person_name(self, firstname_position='before', show_suffix=True, role_recent=True, show_district=False)

    @cache_result
    def name_no_details(self):
        """The person's full name (excluding all title details)."""
        return get_person_name(self, firstname_position='before', show_suffix=True)
        
    @cache_result
    def name_no_details_lastfirst(self):
        return get_person_name(self, firstname_position='after')
            
    @cache_result
    def name_lastfirst_short(self):
        return get_person_name(self, firstname_position='after', firstname_style="nickname")
            
    @cache_result
    def name_and_title(self):
        return get_person_name(self, firstname_position='before', show_suffix=True, role_recent=True, show_party=False, show_district=False)

    @cache_result
    def name_lastonly(self):
        return get_person_name(self, firstname_position='none', show_suffix=False, role_recent=True, show_party=True, show_district=True)

    def set_names(self):
        self.sortname = get_person_name(self, firstname_position='after', role_recent=True, show_district=True, show_title=False, show_type=True)
        self.name = get_person_name(self, firstname_position='before', role_recent=True)

    @property
    def him_her(self):
        return { Gender.male: "him", Gender.female: "her" }.get(self.gender, "them")
    @property
    def his_her(self):
        return { Gender.male: "his", Gender.female: "her" }.get(self.gender, "their")
    @property
    def he_she(self):
        return { Gender.male: "he", Gender.female: "she" }.get(self.gender, "they")
    @property
    def he_she_cap(self):
        return self.he_she[0].upper() + self.he_she[1:]
        
    @property
    def current_role(self):
        return self.get_current_role()
    def get_current_role(self):
        try:
            if not self.roles.all()._result_cache: # if this has already been feteched by prefetch_related
                return self.roles.get(current=True)
            else:
                return [r for r in self.roles.all() if r.current][0]
        except (PersonRole.DoesNotExist, IndexError):
            return None
    def is_currently_serving(self):
        return self.roles.filter(current=True).exists()

    def get_absolute_url(self):
        name = slugify('%s %s' % (self.firstname if not self.firstname.endswith(".") else self.middlename, self.lastname))
        name = name.replace('-', '_')
        return '/congress/members/%s/%d' % (name, self.pk)

    def get_age(self):
        if not self.birthday:
            return 0
        else:
            today = datetime.date.today()
            return relativedelta(today, self.birthday).years

    def roles_condensed(self, round_end=True):
        ret = []
        for role in self.roles.order_by('startdate'):
            role.id = None # prevent corruption
            role.enddate = role.logical_enddate(round_end=round_end)
            if len(ret) > 0 and role.continues_from(ret[-1]):
                ret[-1].enddate = role.enddate
                ret[-1].current |= role.current
                ret[-1].party = role.party # show most recent party
                ret[-1].seniority = None # probably changes
            else:
                ret.append(role)
        ret.reverse()
        return ret

    def get_role_at_date(self, when, congress=None):
        if isinstance(when, datetime.datetime):
            when = when.date()
        
        # A person may have two roles on the same date, such as when simultaneously
        # resigning from the House to take office in the Senate. In that case, return the
        # most recent role.
        for r in self.roles.filter(startdate__lte=when, enddate__gte=when).order_by("-startdate"):
            if congress is not None and r.congress_numbers() is not None and congress not in r.congress_numbers(): continue
            return r
        return None

    def get_last_role_at_congress(self, congress):
        start, end = get_congress_dates(congress)
        try:
            return self.roles.filter(startdate__lte=end, enddate__gte=start).order_by('-startdate')[0]
        except IndexError:
            return None
            
    def get_role_at_year(self, year):
        try:
            return self.roles.filter(startdate__lte=("%d-12-31"%year), enddate__gte=("%d-01-01"%year)).order_by('-startdate')[0]
        except IndexError:
            return None
            
    _most_recent_role = None
    def get_most_recent_role(self):
        if self._most_recent_role: return self._most_recent_role
        try:
            if not self.roles.all()._result_cache: # if this has already been feteched by prefetch_related
                r = self.roles.order_by('-startdate')[0]
            else:
                r = sorted(self.roles.all(), key=lambda r : r.startdate, reverse=True)[0]
            self._most_recent_role = r
            return r
        except IndexError:
            return None
    def get_most_recent_congress_role(self, excl_trivial=False):
        for r in self.roles.filter(role_type__in=(RoleType.senator, RoleType.representative)).order_by('-startdate'):
            if excl_trivial and (r.enddate-r.startdate).days < 100: continue
            return r
        return None

    def get_photo_url(self, size=100):
        """Return URL of 100px photo, or other specified size."""
        return '/data/photos/%d-%dpx.jpeg' % (self.pk, size)
    def get_photo_url_50(self):
        return self.get_photo_url(size=50)
    def get_photo_url_100(self):
        return self.get_photo_url(size=100)
    def has_photo(self, size=100):
        import os.path
        return os.path.exists("." + self.get_photo_url(size=size))

    class Meta:
        pass # ordering = ['lastname', 'firstname'] # causes prefetch related to be slow

    def vote_sources(self):
        from vote.models import Vote
        sources = set()
        for v in Vote.objects.filter(voters__person=self).order_by().values("source").distinct():
            if v["source"] in (1, 2):
                sources.add("congress")
            elif v["source"] == 3:
                sources.add("keithpoole")
        return sources

    def get_photo(self):
        size = 200
        photo_path = 'data/photos/%d-%dpx.jpeg' % (self.pk, size)
        if os.path.exists(photo_path):
            photo_url = '/' + photo_path
            with open(photo_path.replace("-%dpx.jpeg" % size, "-credit.txt"), "r") as f:
                photo_credit = f.read().strip().split(" ", 1)
                return photo_url, photo_credit
        else:
            return None, None

    @staticmethod
    def load_session_stats(session):
      # Which Congress is it?
        for congress, s, sd, ed in get_all_sessions():
            if s == session: break # leaves "congress" variable set
        else:
            raise ValueError("Invalid session: %s" % session)

        fn = "data/us/%d/stats/session-%s.json" % (congress, session)
        try:
            datafile = json.load(open(fn))
            datafile["meta"]["pub_year"] = session
            if datafile["meta"]["is_full_congress_stats"]:
                datafile["meta"]["startdate"] = get_congress_dates(congress)[0]
                datafile["meta"]["enddate"] = get_congress_dates(congress)[1]
            else:
                datafile["meta"]["startdate"] = sd
                datafile["meta"]["enddate"] = ed
        except IOError:
            raise ValueError("No statistics are available for session %s." % session)

        return datafile

    def get_session_stats(self, session):
        datafile = Person.load_session_stats(session)
  
        if str(self.id) not in datafile["people"]:
            raise ValueError("No statistics available for person %d in session %s." % (self.id, session))

        stats = datafile["people"][str(self.id)]
        stats["meta"] = datafile["meta"] # copy this over
        return stats

    def get_feed(self, feed_type="p"):
        if feed_type not in ("p", "pv", "ps"): raise ValueError(feed_type)
        from events.models import Feed
        return Feed.objects.get_or_create(feedname="%s:%d" % (feed_type, self.id))[0]

    @staticmethod
    def from_feed(feed):
        if ":" not in feed.feedname or feed.feedname.split(":")[0] not in ("p", "pv", "ps"): raise ValueError(feed.feedname)
        pid = int(feed.feedname.split(":")[1])
        cache_key = "person:%d" % pid
        p = cache.get(cache_key)
        if not p:
            p = Person.objects.get(id=pid)
            cache.set(cache_key, p, 60*60*4) # 4 hours
        return p

class PersonRole(models.Model):
    """Terms held in office by Members of Congress, Presidents, and Vice Presidents. Each term corresponds with an election, meaning each term in the House covers two years (one 'Congress'), as President/Vice President four years, and in the Senate six years (three 'Congresses')."""
	
    person = models.ForeignKey('person.Person', related_name='roles')
    role_type = models.IntegerField(choices=RoleType, db_index=True, help_text="The type of this role: a U.S. senator, a U.S. congressperson, a U.S. president, or a U.S. vice president.")
    current = models.BooleanField(default=False, choices=[(False, "No"), (True, "Yes")], db_index=True, help_text="Whether the role is currently held, or if this is archival information.")
    startdate = models.DateField(db_index=True, help_text="The date the role began (when the person took office).")
    enddate = models.DateField(db_index=True, help_text="The date the role ended (when the person resigned, died, etc.)")
    # http://en.wikipedia.org/wiki/Classes_of_United_States_Senators
    senator_class = models.IntegerField(choices=SenatorClass, blank=True, null=True, db_index=True, help_text="For senators, their election class, which determines which years they are up for election. (It has nothing to do with seniority.)") # None for representatives
    senator_rank = models.IntegerField(choices=SenatorRank, blank=True, null=True, help_text="For senators, their state rank, i.e. junior or senior. For historical data, this is their last known rank.") # None for representatives
    # http://en.wikipedia.org/wiki/List_of_United_States_congressional_districts
    district = models.IntegerField(blank=True, null=True, db_index=True, help_text="For representatives, the number of their congressional district. 0 for at-large districts, -1 in historical data if the district is not known.") # None for senators/presidents
    state = models.CharField(choices=sorted(statenames.items()), max_length=2, blank=True, db_index=True, help_text="For senators and representatives, the two-letter USPS abbrevation for the state or territory they are serving. Values are the abbreviations for the 50 states (each of which have at least one representative and two senators, assuming no vacancies) plus DC, PR, and the island territories AS, GU, MP, and VI (all of which have a non-voting delegate), and for really old historical data you will also find PI (Philippines, 1907-1946), DK (Dakota Territory, 1861-1889), and OR (Orleans Territory, 1806-1811) for non-voting delegates.")
    party = models.CharField(max_length=255, blank=True, null=True, db_index=True, help_text="The political party of the person. If the person changes party, it is usually the most recent party during this role.")
    caucus = models.CharField(max_length=255, blank=True, null=True, help_text="For independents, the party that the legislator caucuses with. If changed during a term, the most recent.")
    website = models.CharField(max_length=255, blank=True, help_text="The URL to the official website of the person during this role, if known.")
    phone = models.CharField(max_length=64, blank=True, null=True, help_text="The last known phone number of the DC congressional office during this role, if known.")
    leadership_title = models.CharField(max_length=255, blank=True, null=True, help_text="The last known leadership role held during this role, if any.")
    extra = JSONField(blank=True, null=True, help_text="Additional schema-less information stored with this object.")

    # API
    api_recurse_on = ('person',)
    api_additional_fields = {
        "title": "get_title_abbreviated",
        "title_long": "get_title",
        "description": "get_description",
        "congress_numbers": "congress_numbers",
    }
    api_example_parameters = { "current": "true", "sort": "state" }

    class Meta:
        pass # ordering = ['startdate'] # causes prefetch_related to be slow

    def __unicode__(self):
        return '%s / %s to %s / %s / %s' % (self.person.fullname, self.startdate, self.enddate, self.get_role_type_display(), repr(self.congress_numbers()))
       
    def continues_from(self, prev):
        if self.startdate - prev.enddate > datetime.timedelta(days=120): return False
        if self.role_type != prev.role_type: return False
        if self.senator_class != prev.senator_class: return False
        if self.state != prev.state: return False
        if self.district != prev.district: return False
        return True

    def get_title(self):
        """The long form of the title used to prefix the names of people with this role: Representative, Senator, President, Delegate, or Resident Commissioner."""
        return self.get_title_name(short=False)

    def get_title_abbreviated(self):
        """The title used to prefix the names of people with this role: Rep., Sen., President, Del. (delegate), or Commish. (resident commissioner)."""
        return self.get_title_name(short=True)

    def get_title_name(self, short):
        if self.role_type == RoleType.president:
            return 'President' if short else 'President of the United States'
        if self.role_type == RoleType.vicepresident:
            return 'Vice President' if short else 'Vice President of the United States (and President of the Senate)'
        if self.role_type == RoleType.senator:
            return 'Sen.' if short else 'Senator'
        if self.role_type == RoleType.representative:
            if self.state not in stateapportionment:
                # All of the former 'states' were territories that sent delegates.
                return 'Rep.' if short else 'Delegate'
            if self.state == 'PR':
                return 'Commish.' if short else 'Resident Commissioner'
            if stateapportionment[self.state] == 'T':
                return 'Rep.' if short else 'Delegate'
            return 'Rep.' if short else 'Representative'
            
    def state_name(self):
        if not self.state: return "the United States"
        return statenames[self.state]

    def state_name_article(self):
        if not self.state: return "the United States"
        ret = statenames[self.state]
        if self.state in ("DC", "MP", "VI", "PI", "OL"):
            ret = "the " + ret
        return ret
            
    def get_description(self):
        """A description of this role, e.g. Delegate for District of Columbia At Large."""
        
        from django.contrib.humanize.templatetags.humanize import ordinal
        
        if self.role_type in (RoleType.president, RoleType.vicepresident):
            return self.get_title_name(False)
        if self.role_type == RoleType.senator:
            js = ""
            if self.current and self.senator_rank: js = self.get_senator_rank_display() + " "
            return js + self.get_title_name(False) + " from " + statenames[self.state]
        if self.role_type == RoleType.representative:
            if self.district == -1 or stateapportionment.get(self.state) in ("T", None): # unknown district / current territories and former state-things, all of which send/sent delegates
                return self.get_title_name(False) + " for " + self.state_name_article()
            elif self.district == 0:
                return self.get_title_name(False) + " for " + statenames[self.state] + " At Large"
            else:
                return self.get_title_name(False) + " for " + statenames[self.state] + "'s " + ordinal(self.district) + " congressional district"

    def get_description_natural(self):
        """A description of this role in sentence form, e.g. the delegate for the District of Columbia's at-large district."""
        
        from website.templatetags.govtrack_utils import ordinalhtml
        
        if self.role_type in (RoleType.president, RoleType.vicepresident):
            return self.get_title_name(False)
        if self.role_type == RoleType.senator:
            js = "a "
            if self.current and self.senator_rank: js = "the " + self.get_senator_rank_display().lower() + " "
            return js + "senator from " + statenames[self.state]
        if self.role_type == RoleType.representative:
            if stateapportionment.get(self.state) in ("T", None): # current territories and former state-things, all of which send/sent delegates
                return "the %s from %s" % (
                    self.get_title_name(False).lower(),
                    self.state_name_article()
                )
            else:
                if self.district == -1:
                    return "the representative for " + statenames[self.state]
                elif self.district == 0:
                    return "the representative for " + statenames[self.state] + "'s at-large district"
                else:
                    return "the representative for " + statenames[self.state] + "'s " + ordinalhtml(self.district) + " congressional district"

    def congress_numbers(self):
        """The Congressional sessions (Congress numbers) that this role spans, as a list from the starting Congress number through consecutive numbers to the ending Congress number."""
        # Senators can span Congresses, so return a range.
        c1 = get_congress_from_date(self.startdate, range_type="start")
        c2 = get_congress_from_date(self.enddate, range_type="end")
        if not c1 or not c2: return None
        return range(c1, c2+1) # congress number only, not session

    def most_recent_congress_number(self):
        n = self.congress_numbers()
        if not n: return None
        n = n[-1]
        if n > settings.CURRENT_CONGRESS: n = settings.CURRENT_CONGRESS # we don't ever mean to ask for a future one (senators, PR res com)
        return n

    @property
    def leadership_title_full(self):
        if not self.leadership_title: return None
        if self.leadership_title == "Speaker": return "Speaker of the House"
        return RoleType.by_value(self.role_type).congress_chamber + " " + self.leadership_title

    def get_party_on_date(self, when):
        if self.extra and "party_affiliations" in self.extra:
            for pa in self.extra["party_affiliations"]:
                if pa['start'] <= when.date().isoformat() <= pa['end']:
                    return pa['party']
        return self.party

    @property
    def is_territory(self):
        # a current territory
        return stateapportionment.get(self.state) == "T"

    @property
    def is_historical_territory(self):
        # a historical territory
        # note: self.state is "" for presidents/vps
        return self.state and stateapportionment.get(self.state) is None

    def create_events(self, prev_role, next_role):
        now = datetime.datetime.now().date()
        from events.models import Feed, Event
        with Event.update(self) as E:
            f = self.person.get_feed()
            if not prev_role or not self.continues_from(prev_role):
                E.add("termstart", self.startdate, f)
            if not next_role or not next_role.continues_from(self):
                if self.enddate <= now: # because we're not sure of end date until it happens
                    E.add("termend", self.enddate, f)
        
    def render_event(self, eventid, feeds):
        self.person.role = self # affects name generation
        return {
            "type": "Elections and Offices",
            "date_has_no_time": True,
            "date": self.startdate if eventid == "termstart" else self.enddate,
            "title": self.person.name + (" takes office as " if eventid == "termstart" else " leaves office as ") + self.get_description(),
            "url": self.person.get_absolute_url(),
            "body_text_template": "{{name}} {{verb}} {{term}}.",
            "body_html_template": "<p>{{name}} {{verb}} {{term}}.</p>",
            "context": {
                "name": self.person.name,
                "verb": ("takes office as" if eventid == "termstart" else "leaves office as"),
                "term": self.get_description(),
            }
            }

    def logical_dates(self, round_end=False):
        startdate = None
        enddate = None
        prev_role = None
        found_me = False
        for role in self.person.roles.filter(role_type=self.role_type, senator_class=self.senator_class, state=self.state, district=self.district).order_by('startdate'):
            if found_me and not role.continues_from(prev_role):
                break
            if prev_role == None or not role.continues_from(prev_role):
                startdate = role.startdate
            enddate = role.logical_enddate(round_end=round_end)
            prev_role = role
            if role.id == self.id:
                found_me = True
        if not found_me: raise Exception("Didn't find myself?!")
        return (startdate, enddate)

    def logical_enddate(self, round_end=False):
        if round_end and self.enddate.month == 1 and self.enddate.day < 10:
            return datetime.date(self.enddate.year-1, 12, 31)
        return self.enddate

    def next_election_year(self):
        # For current terms, roles end at the end of a Congress on Jan 3.
        # The election occurs in the year before.
        if not self.current: raise ValueError()
        return self.enddate.year-1

    def get_most_recent_session_stats(self):
        # Which Congress and session's end date is the most recently covered by this role?
        errs = []
        congresses = self.congress_numbers()
        for congress, session, sd, ed in reversed(get_all_sessions()):
            if congress not in congresses: continue
            if self.startdate < ed <= self.enddate:
                try:
                    return self.person.get_session_stats(session)
                except ValueError as e:
                    errs.append(unicode(e))
        raise ValueError("No statistics are available for this role: %s" % "; ".join(errs))

    def opposing_party(self):
        if self.party == "Democrat": return "Republican"
        if self.party == "Republican": return "Democrat"
        return None

    def get_sort_key(self):
        # As it happens, our enums define a good sort order between senators and representatives.
        return (self.role_type, self.senator_rank)

# Feeds

from events.models import Feed
Feed.register_feed(
    "p:",
    title = lambda feed : Person.from_feed(feed).name,
    noun = "person",
    includes = lambda feed : [Person.from_feed(feed).get_feed("pv"), Person.from_feed(feed).get_feed("ps")],
    link = lambda feed: Person.from_feed(feed).get_absolute_url(),
    scoped_title = lambda feed : "All Events for " + Person.from_feed(feed).lastname,
    category = "federal-other",
    description = "You will get updates about major activity on sponsored bills and how this Member of Congress votes in roll call votes.",
    is_subscribable = lambda feed : Person.from_feed(feed).get_current_role() is not None,
    track_button_noun = lambda feed : Person.from_feed(feed).him_her,
    )
Feed.register_feed(
    "ps:",
    title = lambda feed : Person.from_feed(feed).name + " - Bills Sponsored",
    noun = "person",
    link = lambda feed: Person.from_feed(feed).get_absolute_url(),
    scoped_title = lambda feed : Person.from_feed(feed).lastname + "'s Sponsored Bills",
    category = "federal-bills",
    description = "You will get updates about major activity on bills sponsored by this Member of Congress.",
    )
Feed.register_feed(
    "pv:",
    title = lambda feed : Person.from_feed(feed).name + " - Voting Record",
    noun = "person",
    link = lambda feed: Person.from_feed(feed).get_absolute_url(),
    scoped_title = lambda feed : Person.from_feed(feed).lastname + "'s Voting Record",
    single_event_type = True,
    category = "federal-votes",
    description = "You will get updates on how this Member of Congress votes in roll call votes.",
)

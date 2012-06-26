# -*- coding: utf-8 -*-
from django.db import models
from django.core.urlresolvers import reverse
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.contrib.auth.models import User
from django.utils.text import truncate_words

import re
import urllib
from datetime import datetime, timedelta

class Feed(models.Model):
    """Each Feed has a code name that can be used to reconstruct information about the feed."""
    feedname = models.CharField(max_length=64, unique=True, db_index=True)
    
    def __unicode__(self):
        return self.feedname

    @staticmethod
    def from_name(feedname):
        return Feed.objects.get(feedname=feedname)

    @staticmethod
    def get_events_for(feeds, count):
        # This method returns the most recent events matching a set of feeds,
        # or all events if feeds is None. Feeds is an iterable of Feed objects
        # or str's of Feed feednames, which must exist.
        
        if feeds != None:
            feeds = expand_feeds(feeds)
        
        from django.db import connection, transaction
        cursor = connection.cursor()

        # Our table has multiple entries for each event, one entry for each feed it is a
        # part of. Thus, if we query on no feeds or on multiple feeds, we have to make
        # the results distinct. The Django ORM can't handle generating a nice query for this:
        # It adds joins that ruin indexing. So we handle this by querying in batches until
        # we get 'count' distinct events.
        #
        # Additionally, MySQL doesnt do indexing well if we query on multiple feeds at once.
        # In that case, we take a different code path and find 'count' events from each feed,
        # then put them together, sort, distinct, and take the most recent 'count' items.

        if not feeds or len(feeds) == 0:
            # pull events in batches, eliminating duplicate results (events in multiple feeds),
            # which is done faster here than in MySQL.
            start = 0
            size = count * 2
            ret = []
            seen = set()
            while len(ret) < count:
                cursor.execute("SELECT source_content_type_id, source_object_id, eventid, `when` FROM events_event ORDER BY `when` DESC, source_content_type_id DESC, source_object_id DESC, seq DESC LIMIT %s OFFSET %s ", [size, start])
                
                batch = cursor.fetchall()
                for b in batch:
                    if not b in seen:
                        ret.append( { "source_content_type": b[0], "source_object_id": b[1], "eventid": b[2], "when": b[3] } )
                        seen.add(b)
                if len(batch) < size: break # no more items
                start += size
                size *= 2
            
            return ret
        
        else:
            # pull events by feed. When we query on the 'seq' column, MySQL uses the when-based
            # index rather than the feed-based index, which causes a big problem if there are
            # no recent events.
            ret = []
            seen = { }
            for feed in feeds:
                cursor.execute("SELECT source_content_type_id, source_object_id, eventid, `when`, seq FROM events_event WHERE feed_id = %s ORDER BY `when` DESC, source_content_type_id DESC, source_object_id DESC LIMIT %s", [feed.id, count])
                
                batch = cursor.fetchall()
                for b in batch:
                    key = tuple(b[0:3]) # the unique part for identifying the event
                    if not key in seen:
                        v = { "source_content_type": b[0], "source_object_id": b[1], "eventid": b[2], "when": b[3], "seq": b[4], "feeds": set() }
                        ret.append(v)
                        seen[key] = v
                    seen[key]["feeds"].add(feed)
                        
            ret.sort(key = lambda x : (x["when"], x["source_content_type"], x["source_object_id"], x["seq"]), reverse=True)
            
            return ret
        
    def get_events(self, count):
        return Feed.get_events_for((self,), count)

    def get_five_events(self):
        return self.get_events(5)
    def get_ten_events(self):
        return self.get_events(10)

    # feed metadata
    
    feed_metadata = {
        "misc:activebills": {
            "title": "Major Activity on All Legislation",
            "slug": "bill-activity",
            "intro_html": """<p>This feed tracks all major activity on legislation, including newly introduced bills and resolutions, votes on bills and resolutions, enacted bills, and other such events.</p> <p>To exclude newly introduced bills and resolutions, use the <a href="/events/major-bill-activity">Major Activity on All Legislation Except New Introductions</a> feed.</p> <p>You can also browse bills and filter by status using <a href="/congress/bills/browse">advanced bill search</a>.</p>""",
            "breadcrumbs": [("/congress", "Congress"), ("/congress/bills", "Bills")],
        },
        "misc:enactedbills": {
            "title": "Enacted Bills",
            "slug": "enacted-bills",
            "intro_html": """<p>This feed tracks the enactment of bills either by the the signature of the president or a veto override.</p> <p>You can also <a href="/congress/bills/browse?status=28,29">browse enacted bills</a> using advanced bill search.</p>""",
            "breadcrumbs": [("/congress", "Congress"), ("/congress/bills", "Bills")],
        },
        "misc:introducedbills": {
            "title": "Introduced Bills and Resolutions",
            "slug": "introduced-bills",
            "intro_html": """<p>This feed tracks newly introduced bills and resolutions.</p> <p>You can also <a href="/congress/bills/browse?sort=-introduced_date">browse introduced bills</a> using advanced bill search.</p>""",
            "breadcrumbs": [("/congress", "Congress"), ("/congress/bills", "Bills")],
        },
        "misc:activebills2": {
            "title": "Major Activity on All Legislation Except New Introductions",
            "slug": "major-bill-activity",
            "intro_html": """<p>This feed tracks major activity on legislation, including votes on bills and resolutions, enacted bills, and other such events.</p> <p>This feed includes all of the same events as the <a href="/events/bill-activity">Major Activity on All Legislation</a> feed except newly introduced bills and resolutions.</p> <p>You can also browse bills and filter by status using <a href="/congress/bills/browse">advanced bill search</a>.</p>""",
            "breadcrumbs": [("/congress", "Congress"), ("/congress/bills", "Bills")],
        },
        "misc:comingup": {
            "title": "Legislation Coming Up",
            "slug": "coming-up",
            "intro_html": """<p>This feed tracks legislation posted on the House Majority Leader&rsquo;s week-ahead website at <a href="http://docs.house.gov">docs.house.gov</a> and the <a href="http://www.senate.gov/pagelayout/legislative/d_three_sections_with_teasers/calendars.htm">Senate Floor Schedule</a> which gives rough one-day-ahead notice.</p> <p>You can also browse bills and filter by status using <a href="/congress/bills/browse">advanced bill search</a>.</p>""",
            "breadcrumbs": [("/congress", "Congress"), ("/congress/bills", "Bills")],
        },
        "misc:allcommittee": {
            "title": "Committee Meetings",
            "link": "/congress/committees",
        },
        "misc:allvotes": {
            "title": "Roll Call Votes",
            "link": "/congress/votes",
        },
        "bill:": {
            "title": lambda self : truncate_words(self.bill().title, 12),
            "noun": "bill",
            "link": lambda self: self.bill().get_absolute_url(),
        },
        "p:": {
            "title": lambda self : self.person().name,
            "noun": "person",
            "includes": lambda self : [Feed.PersonVotesFeed(self.person()), Feed.PersonSponsorshipFeed(self.person())],
            "link": lambda self: self.person().get_absolute_url(),
        },
        "ps:": {
            "title": lambda self : self.person().name + " - Bills Sponsored",
            "noun": "person",
            "link": lambda self: self.person().get_absolute_url(),
        },
        "pv:": {
            "title": lambda self : self.person().name + " - Voting Record",
            "noun": "person",
            "link": lambda self: self.person().get_absolute_url(),
        },
        "committee:": {
            "title": lambda self : truncate_words(self.committee().fullname, 12),
            "noun": "committee",
            "includes": lambda self : [Feed.CommitteeBillsFeed(self.committee()), Feed.CommitteeMeetingsFeed(self.committee())],
            "link": lambda self: self.committee().get_absolute_url(),
        },
        "committeebills:": {
            "title": lambda self : "Bills in " + truncate_words(self.committee().fullname, 12),
            "noun": "committee",
            "link": lambda self: self.committee().get_absolute_url(),
        },
        "committeemeetings:": {
            "title": lambda self : "Meetings for " + truncate_words(self.committee().fullname, 12),
            "noun": "committee",
            "link": lambda self: self.committee().get_absolute_url(),
        },
        "crs:": {
            "title": lambda self : self.issue().name,
            "noun": "subject area",
            "link": lambda self: self.issue().get_absolute_url(),
        }
    }
    
    @staticmethod
    def register_feed(prefix, **metadata):
        """Registers a feed with the events module. Keyword arguments must include:
        
              title = string or function (taking the feed object as an argument)
              
          And may include:
          
              noun = string
                       The type of object this feed is about, e.g. "person"
              
              link = string or function (taking the feed object as an argument)
                     If slug is set, then the link is generated automatically.
                     If neither link nor slug is set, then this feed has no link.
                     
              slug = string
                     Used for feeds with no internal parameters that have a dedicated
                     page generated by this module at /events/{slug}.
              intro_html = string
                     If slug is set, use this to provide HTML for the page for the
                     feed generated by this module.
              breadcrumbs = list of tuples of (link, text)
        """
        Feed.feed_metadata[prefix] = metadata
     
        
    def type_metadata(self):
        if self.feedname in Feed.feed_metadata:
            return Feed.feed_metadata[self.feedname]
        if ":" in self.feedname:
            t = self.feedname.split(":")[0]
            if t+":" in Feed.feed_metadata:
                return Feed.feed_metadata[t+":"]
        return { }
        
    # constructors for feeds

    @staticmethod # private method
    def get_noarg_feed(feedname):
        feed, is_new = Feed.objects.get_or_create(feedname=feedname)
        return feed

    @staticmethod
    def ActiveBillsFeed():
        return Feed.get_noarg_feed("misc:activebills")
    
    @staticmethod
    def EnactedBillsFeed():
        return Feed.get_noarg_feed("misc:enactedbills")
    
    @staticmethod
    def IntroducedBillsFeed():
        return Feed.get_noarg_feed("misc:introducedbills")
    
    @staticmethod
    def ActiveBillsExceptIntroductionsFeed():
        return Feed.get_noarg_feed("misc:activebills2")
    
    @staticmethod
    def ComingUpFeed():
        return Feed.get_noarg_feed("misc:comingup")
    
    @staticmethod
    def AllCommitteesFeed():
        return Feed.get_noarg_feed("misc:allcommittee")
    
    @staticmethod
    def AllVotesFeed():
        return Feed.get_noarg_feed("misc:allvotes")

    # constructors that take object instances, object IDs, or the encoded
    # object reference used in feed names and returns (possibly creating)
    # a Feed object.
    
    @staticmethod # private method
    def get_arg_feed(prefix, objclass, id_ref_instance, dereference, reference):
        # Always dereference id's and references before get_or_created to
        # prevent the creation of feeds that do not correspond with objects.
        if isinstance(id_ref_instance, (int, long)):
            obj = objclass.objects.get(pk=id_ref_instance)
        elif isinstance(id_ref_instance, (str, unicode)):
            obj = dereference(id_ref_instance)
        elif type(id_ref_instance) == objclass:
            obj = id_ref_instance
        else:
            raise ValueError(unicode(id_ref_instance))
       
        feedname = prefix + ":" + reference(obj)
        feed, is_new = Feed.objects.get_or_create(feedname=feedname)
        feed._ref = obj
        return feed

    @staticmethod
    def _PersonFeed(prefix, id_ref_instance):
        from person.models import Person
        return Feed.get_arg_feed(prefix, Person, id_ref_instance,
            lambda id : Person.objects.get(id=id),
            lambda p : str(p.id))

    @staticmethod
    def PersonFeed(id_ref_instance):
        return Feed._PersonFeed("p", id_ref_instance)
        
    @staticmethod
    def PersonVotesFeed(id_ref_instance):
        return Feed._PersonFeed("pv", id_ref_instance)
        
    @staticmethod
    def PersonSponsorshipFeed(id_ref_instance):
        return Feed._PersonFeed("ps", id_ref_instance)
    
    @staticmethod
    def BillFeed(id_ref_instance):
        from bill.models import Bill, BillType
        def dereference(ref):
            m = re.match(r"([a-z]+)(\d+)-(\d+)", ref)
            bill_type = BillType.by_xml_code(m.group(1))
            bill = Bill.objects.get(congress=m.group(2), bill_type=bill_type, number=m.group(3))
            return bill
        def reference(bill):
            bt = BillType.by_value(bill.bill_type)
            return bt.xml_code + str(bill.congress) + "-" + str(bill.number)
        return Feed.get_arg_feed("bill", Bill, id_ref_instance,
            dereference,
            reference)

    @staticmethod
    def IssueFeed(id_ref_instance):
        from bill.models import BillTerm
        def dereference(ref):
            if ref.isdigit():
                return BillTerm.objects.get(id=int(ref))
            return BillTerm.objects.get(name=ref)
        return Feed.get_arg_feed("crs", BillTerm, id_ref_instance,
            dereference,
            lambda ix : str(ix.id))
        
    @staticmethod
    def CommitteeFeed(id_ref_instance):
        from committee.models import Committee
        return Feed.get_arg_feed("committee", Committee, id_ref_instance,
            lambda ref : Committee.objects.get(code=ref),
            lambda obj : obj.code)

    @staticmethod
    def CommitteeBillsFeed(id_ref_instance):
        from committee.models import Committee
        return Feed.get_arg_feed("committeebills", Committee, id_ref_instance,
            lambda ref : Committee.objects.get(code=ref),
            lambda obj : obj.code)

    @staticmethod
    def CommitteeMeetingsFeed(id_ref_instance):
        from committee.models import Committee
        return Feed.get_arg_feed("committeemeetings", Committee, id_ref_instance,
            lambda ref : Committee.objects.get(code=ref),
            lambda obj : obj.code)
        
    # DistrictFeed?
    
    # accessor methods
    
    @property
    def title(self):
        m = self.type_metadata()
        if "title" not in m: return unicode(self)
        if callable(m["title"]):
            return m["title"](self)
        return m["title"]
        
    @property
    def link(self):
        m = self.type_metadata()
        if "slug" in m: return "/events/" + m["slug"]
        if "link" not in m: return None
        if not callable(m["link"]): return m["link"]
        return m["link"](self)
        
    @property
    def view_url(self):
        return "/events?feeds=" + urllib.quote(self.feedname)
    
    @property
    def rss_url(self):
        return "/events/events.rss?feeds=" + urllib.quote(self.feedname)

    def includes_feeds(self):
        m = self.type_metadata()
        if "includes" not in m: return []
        if callable(m["includes"]):
            return m["includes"](self)
        return m["includes"]

    def includes_feeds_and_self(self):
        return [self] + self.includes_feeds()

    def bill(self):
         if not hasattr(self, "_ref"):
               if ":" in self.feedname and self.feedname.split(":")[0] in ("bill",):
                    from bill.models import Bill, BillType
                    m = re.match(r"([a-z]+)(\d+)-(\d+)", self.feedname.split(":")[1])
                    bill_type = BillType.by_xml_code(m.group(1))
                    return Bill.objects.get(congress=m.group(2), bill_type=bill_type, number=m.group(3))
               else:
                    self._ref = None
         return self._ref

    def person(self):
         if not hasattr(self, "_ref"):
               if ":" in self.feedname and self.feedname.split(":")[0] in ("p", "pv", "ps"):
                    import person.models
                    return person.models.Person.objects.get(id=self.feedname.split(":")[1])
               else:
                    self._ref = None
         return self._ref
         
    def committee(self):
         if not hasattr(self, "_ref"):
               if ":" in self.feedname and self.feedname.split(":")[0] in ("committee", "committeebills", "committeemeetings"):
                    import committee.models
                    return committee.models.Committee.objects.get(code=self.feedname.split(":")[1])
               else:
                    self._ref = None
         return self._ref
         
    def issue(self):
         if not hasattr(self, "_ref"):
               if ":" in self.feedname and self.feedname.split(":")[0] in ("crs",):
                    import bill.models
                    return bill.models.BillTerm.objects.get(id=self.feedname.split(":")[1])
               else:
                    self._ref = None
         return self._ref
         
class Event(models.Model):
    """
    Holds info about an event in a feed. This record doesn't contain any information about
    the event itself except the date of the event so that records can be efficiently queried by date.
    
    The primary key is used as a monotonically increasing sequence number for all records so that
    we can reliably track which events a user has been notified about by tracking the highest
    primary key the user has seen.
    
    Events are created by source objects. A Vote, for instance, creates an Event record
    for itself, actually multiple Event records one for each feed the event goes into: the
    all votes feed and the votes feeds for each Member of Congress that voted. The Event
    refers back to the Vote via the source generic relationship. Information about the event
    so that it can be displayed is obtained by calling Event.render(), which in turn queries
    the source object for information about the vote.
    
    The source object must have a method render_event(eventid, feeds) which returns
    a dict containing the keys:
        type: a string describing the type of the event, for display purposes
        date: a datetime that the event took place (same as Event.when)
        title: a string
        url: a string giving a link URL for the event, starting with the URL's path (i.e. omit scheme & host)
        body_text_template: a Django template used to render the event for text-only presentation (use "|safe" to prevent autoescaping)
        body_html_template: a Django template used to render the event in HTML
        context: a dict passed as the template context when rendering either of the body templates
    And optionally:
        date_has_no_time: set to True to indicate the date on this event has no time associated with it
        
    Some source objects generate multiple events. In this case, it uses the eventid CharField
    to track which event is which. It can put anything in the CharField up to 32 characters.
    For instance, Committee instances generate events for each CommitteeMeeting and code
    each as mtg_ID where ID is the CommitteeMeeting primary key. When its render_event
    is called, it is passed back the eventid so it knows what event it is rendering.
    
    Since some events are only tied to a date, without a time, yet they may have an order, the seq
    field records the order of related events from a single source. The seq field must be constant
    across event instances in the table in multiple fields, otherwise we have a problem using DISTINCT.
    
    To create events, do something like the following, which begins the update process for
    the source object (self) and adds a single event (with eventid "vote") to multiple feeds.
    Note that Event.update() will clear out any previously created events for the source
    object if they are not re-added here.
        from events.feeds import AllVotesFeed, PersonVotesFeed
        from events.models import Event
        with Event.update(self) as E:
            E.add("vote", self.created, AllVotesFeed())
            for v in self.voters.all():
                E.add("vote", self.created, PersonVotesFeed(v.person_id))
                
    Event.render is optionally passed a keyword argument feeds which is a sequence of
    feed.Feed objects that allow the event's template to be customized depending on which
    feed(s) the event is in.
    """
    
    feed = models.ForeignKey(Feed)

    source_content_type = models.ForeignKey(ContentType)
    source_object_id = models.PositiveIntegerField()
    source = generic.GenericForeignKey('source_content_type', 'source_object_id')
    eventid = models.CharField(max_length=32) # unique w.r.t. the source object 

    when = models.DateTimeField(db_index=True)
    seq = models.IntegerField()
    
    @staticmethod
    def sourcearg(source):
        return {
            "source_content_type": ContentType.objects.get_for_model(source),
            "source_object_id": source.id,
            }

    class Meta:
        ordering = ['-id']
        unique_together = (
             ('source_content_type', 'source_object_id', 'eventid', 'feed'),
             ('feed', 'id'),
             ('feed', 'when', 'source_content_type', 'source_object_id', 'eventid'),
             ('when', 'source_content_type', 'source_object_id', 'seq'))
    
    def __unicode__(self):
        return unicode(self.source) + " " + unicode(self.eventid) + " / " + unicode(self.feed)
        
    def render(self, feeds=None):
        return self.source.render_event(self.eventid, feeds)
    
    # This is used to update the events for an object and delete any events that are not updated.
    class update:
        def __init__(self, source):
            self.source = source
            
            # get a list of events previously created for this source so that if they
            # are not updated we can delete them
            self.existing_events = {}
            for event in Event.objects.filter(**Event.sourcearg(source)):
                self.existing_events[event.id] = True
            self.seq = { }

        def __enter__(self):
            return self
            
        def add(self, eventid, when, feed):
            # If feed is a list or tuple, then call this on each item in the list/tuple.
            if isinstance(feed, list) or isinstance(feed, tuple):
                for f in feed:
                    self.add(eventid, when, f)
                return
                
            # Track the sequence number for this eventid, increment in insertion order.
            if not eventid in self.seq: self.seq[eventid] = len(self.seq)
            
            # Create the record for this event for this feed, if it does not exist.
            event, created = Event.objects.get_or_create(
                feed = feed,
                eventid = eventid,
                defaults = {"when": when, "seq": self.seq[eventid]},
                **Event.sourcearg(self.source)
                )
            if not created and event.id in self.existing_events:
                del self.existing_events[event.id] # i.e. don't delete this event on __exit__
                if event.when != when: # update this if it changed
                    event.when = when
                    event.save()
            
        def __exit__(self, type, value, traceback):
            # Clear out any events that were not updated.
            Event.objects.filter(id__in=self.existing_events).delete()
            return False

class SubscriptionList(models.Model):
    # see send_email_updates.py
    EMAIL_CHOICES = [(0, 'No Email Updates'), (1, 'Daily'), (2, 'Weekly')]
    
    user = models.ForeignKey(User, db_index=True, related_name="subscription_lists")
    name = models.CharField(max_length=64)
    trackers = models.ManyToManyField(Feed)
    is_default = models.BooleanField(default=False)
    email = models.IntegerField(default=0, choices=EMAIL_CHOICES)
    last_event_mailed = models.IntegerField(blank=True, null=True) # id of last event
    last_email_sent = models.DateTimeField(blank=True, null=True) # date of last email update sent
    public_id = models.CharField(max_length=16, blank=True, null=True, db_index=True)
    
    class Meta:
        unique_together = [('user', 'name')]

    def get_public_id(self):
        if not self.public_id:
            from random import choice
            import string
            self.public_id = ''.join([choice(string.letters + string.digits) for i in range(16)])
            self.save()
        return self.public_id

    def get_new_events(self):
        feeds = expand_feeds(self.trackers.all())
        if len(feeds) == 0: return None, []
        
        from django.db import connection, transaction
        cursor = connection.cursor()

        # Temporary workaround. Get the maximum id for the event corresponding to
        # last_event_mailed.
        if self.last_event_mailed:
            try:
                e = Event.objects.get(id=self.last_event_mailed)
                e2 = Event.objects.filter(source_content_type=e.source_content_type, source_object_id=e.source_object_id, eventid=e.eventid).order_by('-id')[0]
                self.last_event_mailed = e2.id
            except Event.DoesNotExist:
                pass # hmm, that is odd
        
        # Pull events that this list has not seen yet according to last_event_mailed,
        # but not going back further than a certain period of time, so that if past
        # events are added we don't overflow the user with new events that are actually
        # archival data. Also, the first email update for a user will go back that time
        # period unless we set last_event_mailed.
        
        # The Django ORM can't handle generating a nice query. It adds joins that ruin indexing.
        cursor.execute("SELECT id, source_content_type_id, source_object_id, eventid, `when`, seq, feed_id FROM events_event WHERE id > %s AND `when` > %s AND feed_id IN (" + ",".join(str(f.id) for f in feeds) + ") ORDER BY `when`, source_content_type_id, source_object_id, seq", [self.last_event_mailed if self.last_event_mailed else 0, datetime.now() - timedelta(days=4 if self.email == 1 else 14)])
        
        max_id = None
        ret = []
        seen = { } # uniqify because events are duped for each feed they are in, but track which feeds generated the events
        feedmap = dict((f.id, f) for f in feeds)
        batch = cursor.fetchall()
        for b in batch:
            key = b[1:3] # get the part that uniquely identifies the event, across feeds
            max_id = max(max_id, b[0]) # since we return one event record randomly out of
                                       # all of the dups for the feeds for all records,
                                       # make sure we return the max of the ids, or else
                                       # we might re-send an event in an email.
            if not key in seen:
                v = { "id": b[0], "source_content_type": b[1], "source_object_id": b[2], "eventid": b[3], "when": b[4], "seq": b[5], "feeds": set() }
                ret.append(v)
                seen[key] = v
            v["feeds"].add(feedmap[b[6]])
                
        ret.sort(key = lambda x : (x["when"], x["source_content_type"], x["source_object_id"], x["seq"]))
    
        return max_id, ret
        
def expand_feeds(feeds):
    # Some feeds include the events of other feeds.
    # Tail-recursively expand the feeds.
    feeds = [f if isinstance(f, Feed) else Feed.objects.get(feedname=f) for f in feeds]
    i = 0
    while i < len(feeds):
        meta = feeds[i].type_metadata()
        if "includes" in meta:
            feeds.extend(meta["includes"](feeds[i]))
        i += 1
    return feeds


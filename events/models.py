# -*- coding: utf-8 -*-
from django.db import models
from django.core.urlresolvers import reverse
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.contrib.auth.models import User
from django.utils.text import truncate_words

import re
import urllib

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
            # Some feeds include the events of other feeds.
            # Tail-recursively expand the feeds.
            feeds = [f if isinstance(f, Feed) else Feed.objects.get(feedname=f) for f in feeds]
            i = 0
            while i < len(feeds):
                meta = feeds[i].type_metadata()
                if "includes" in meta:
                    feeds.extend(meta["includes"](feeds[i]))
                i += 1
        
        from django.db import connection, transaction
        cursor = connection.cursor()
        
        # pull events in batches, eliminating duplicate results (events in multiple feeds),
        # which is done faster here than in MySQL.
        start = 0
        size = count * 2
        ret = []
        seen = set()
        while len(ret) < count:
            # The Django ORM can't handle generating a nice query. It adds joins that ruin indexing.
            cursor.execute("SELECT source_content_type_id, source_object_id, eventid, `when` FROM events_event " + ("" if not feeds or len(feeds) == 0 else "WHERE feed_id IN (" + ",".join(str(f.id) for f in feeds) + ")") + " ORDER BY `when` DESC, source_content_type_id DESC, source_object_id DESC, seq DESC LIMIT %s OFFSET %s ", [size, start])
            
            batch = cursor.fetchall()
            for b in batch:
                if not b in seen:
                    ret.append( { "source_content_type": b[0], "source_object_id": b[1], "eventid": b[2], "when": b[3] } )
                    seen.add(b)
            if len(batch) < size: break # no more items
            start += size
            size *= 2
        
        return ret
        
    def get_events(self, count):
        return Feed.get_events_for((self,), count)

    def get_five_events(self):
        return self.get_events(5)

    # feed metadata
    
    feed_metadata = {
        "misc:activebills": {
            "title": "All Activity on Legislation",
        },
        "misc:enactedbills": {
            "title": "Enacted Bills",
        },
        "misc:introducedbills": {
            "title": "Introduced Bills and Resolutions",
        },
        "misc:activebills2": {
            "title": "Activity on Legislation Except New Introductions",
        },
        "misc:allcommittee": {
            "title": "Committee Activity",
        },
        "misc:allvotes": {
            "title": "Roll Call Votes",
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
        if "link" not in m: return None
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
    EMAIL_CHOICES = [(0, 'No Email Updates'), (1, 'Daily'), (2, 'Weekly')]
    
    user = models.ForeignKey(User, db_index=True)
    name = models.CharField(max_length=64)
    trackers = models.ManyToManyField(Feed)
    is_default = models.BooleanField(default=False)
    email = models.IntegerField(default=0, choices=EMAIL_CHOICES)
    last_event_mailed = models.IntegerField(blank=True, null=True) # id of last event
    
    class Meta:
        unique_together = [('user', 'name')]


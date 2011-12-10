# -*- coding: utf-8 -*-
from django.db import models
from django.core.urlresolvers import reverse
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic

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
    def get_events_for(feeds):
        # This method returns the events in a set of feeds. Because
        # events can occur in multiple feeds, values(...).distinct() is
        # used to return a distinct set of events.
        
        qs = Event.objects.all()
        qs = qs.order_by("-when", "-id") # non-timed events should be sorted in database insertion order 
        
        if feeds != None:
            # Some feeds include the events of other feeds.
            # Tail-recursively expand the feeds.
            feeds = list(feeds)
            i = 0
            while i < len(feeds):
                meta = feeds[i].type_metadata()
                if "includes" in meta:
                    feeds.extend(meta["includes"](feeds[i]))
                i += 1
                
            # and apply the filter.
            qs = qs.filter(feed__in=feeds)
        
        # this causes the QuerySet to return dicts rather than Events.
        qs = qs.values("source_content_type", "source_object_id", "eventid", "when").distinct()
        
        return qs
        
    def get_events(self):
        return Feed.get_events_for((self,))
        
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
        "p:": {
            "title": lambda self : self.person().name,
            "noun": "person",
            "includes": lambda self : [Feed.PersonVotesFeed(self.person()), Feed.PersonSponsorshipFeed(self.person())],
        },
        "ps:": {
            "title": lambda self : self.person().name + " - Bills Sponsored",
            "noun": "person",
        },
        "pv:": {
            "title": lambda self : self.person().name + " - Voting Record",
            "noun": "person",
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
        if type(id_ref_instance) == int:
            obj = objclass.objects.get(pk=id_ref_instance)
        elif type(id_ref_instance) == str:
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
    def view_url(self):
        return "/events?feeds=" + urllib.quote(self.feedname)
    
    @property
    def rss_url(self):
        return "/events/events.rss?feeds=" + urllib.quote(self.feedname)
    
    def person(self):
         if not hasattr(self, "_ref"):
               if ":" in self.feedname and self.feedname.split(":")[0] in ("p", "pv", "ps"):
                    import person.models
                    return person.models.Person.objects.get(id=self.feedname.split(":")[1])
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
             ('feed', 'when', 'source_content_type', 'source_object_id', 'eventid'))
    
    def __unicode__(self):
        return unicode(self.source) + " " + unicode(self.eventid) + " / " + unicode(self.feed)
        
    def render(self, feeds=None):
        if self.source == None: print self.id
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
                
            try:
                self.next_id = Event.objects.order_by('-id')[0].id + 1
            except IndexError:
                self.next_id = 1

        def __enter__(self):
            return self
            
        def add(self, eventid, when, feed):
            # If feed is a list or tuple, then call this on each item in the list/tuple.
            if isinstance(feed, list) or isinstance(feed, tuple):
                for f in feed:
                    self.add(eventid, when, f)
                return
            
            # Create the record for this event for this feed, if it does not exist.
            event, created = Event.objects.get_or_create(
                feed = feed,
                eventid = eventid,
                defaults = {"id": self.next_id, "when": when},
                **Event.sourcearg(self.source)
                )
            if created:
                self.next_id += 1
            elif event.id in self.existing_events:
                del self.existing_events[event.id] # i.e. don't delete this event on __exit__
                if event.when != when: # update this if it changed
                    event.when = when
                    event.save()
            
        def __exit__(self, type, value, traceback):
            # Clear out any events that were not updated.
            Event.objects.filter(id__in=self.existing_events).delete()
            return False


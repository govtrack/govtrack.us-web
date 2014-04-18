# -*- coding: utf-8 -*-
from django.db import models, DatabaseError
from django.core.urlresolvers import reverse
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.contrib.auth.models import User

import re
import urllib
from datetime import datetime, timedelta

class Feed(models.Model):
    """Each Feed has a code name that can be used to reconstruct information about the feed."""
    feedname = models.CharField(max_length=64, unique=True, db_index=True)
    
    def __unicode__(self):
        return self.feedname
        
    def tracked_in_lists_with_email(self):
        return self.tracked_in_lists.filter(email__gt=0)

    @staticmethod
    def from_name(feedname, must_exist=True):
        if not must_exist:
            # Return fast.
            return Feed(feedname=feedname)
                
        try:
            return Feed.objects.get(feedname=feedname)
        except Feed.DoesNotExist:
            # Certain feeds aren't in the db. Try a db lookup first, then...
            for feedname2, feedmeta in Feed.feed_metadata.items():
                if feedname.startswith(feedname2) and feedmeta.get("meta", False):
                    return Feed(feedname=feedname)
            raise

    @staticmethod
    def get_events_for(feeds, count):
        # This method returns the most recent events matching a set of feeds,
        # or all events if feeds is None. Feeds is an iterable of Feed objects
        # or str's of Feed feednames, which must exist.
        
        source_feed_map = { }
        if feeds != None:
            feeds, source_feed_map = expand_feeds(feeds)
            feeds = [f for f in feeds if f.id] # filter out only feeds that are in the database
            if len(feeds) == 0:
                return []
        
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

        if feeds == None:
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
                    seen[key]["feeds"].add(source_feed_map.get(feed, feed))
                        
            ret.sort(key = lambda x : (x["when"], x["source_content_type"], x["source_object_id"], x["seq"]), reverse=True)
            
            return ret[0:count]
        
    def get_events(self, count):
        return Feed.get_events_for((self,), count)

    def get_five_events(self):
        return self.get_events(5)
    def get_ten_events(self):
        return self.get_events(10)

    @staticmethod
    def get_trending_feeds():
        def get_feed_counts(num_days):
            # Get the number of new subscriptions to all feeds in the last some days.
            # We don't have a model for the relationship, but we have a table that
            # adds date_added automatically as a timestamp. If we add a 'through'
            # model, we have to replace .add/.remove on the field with other methods.
            try:
                from django.db import connection
                cursor = connection.cursor()
                cursor.execute("SELECT feed_id, count(*) FROM events_subscriptionlist_trackers WHERE date_added > %s GROUP BY feed_id", [datetime.now() - timedelta(days=num_days)])
                subs = cursor.fetchall()
                return { row[0]: row[1] for row in subs } 
            except DatabaseError as e:
                # The database table hasn't been configured with the date_added column,
                # which is hidden from the Django ORM at the moment.
                print "Database isn't configured with date_added column in events_subscriptionlist_trackers."
                return None
                
        trending = []
        for period in (2, 6, 11, 23):
            # Get the number of times each feed was subscribed to in the last period and 2*period days.
            subs1 = get_feed_counts(period)
            subs2 = get_feed_counts(period*2)
            if subs1 == None or subs2 == None: return [] # database not configured
            
            # Order the mentioned feeds by the ratio of recent subscriptions to less recent subscriptions,
            # but giving a boost for the total number of new subscriptions.
            mv = float(max(subs1.values()))
            feeds = sorted(subs1.keys(), key = lambda f : subs1[f]/subs2.get(f, 1) + 2*(subs1[f]/mv)**.5, reverse=True)
            
            # Take the top trending bill not seen in a previous period.
            for f in feeds:
                if f not in trending:
                    trending.append(f)
                    break
        return trending

    # feed metadata
    
    feed_metadata = {
        "misc:activebills": {
            "title": "All Legislative Activity",
            "slug": "bill-activity",
            "simple": True,
            "sort_order": 105,
            "category": "federal-bills",
            "description": "Get an update when any bill is introduced, scheduled for debate, or has major action such as a vote or being enacted.",
        },
        "misc:enactedbills": {
            "title": "New Laws",
            "slug": "enacted-bills",
            "simple": True,
            "single_event_type": True,
            "sort_order": 104,
            "category": "federal-bills",
            "description": "You will be alerted every time a law is enacted.",
        },
        "misc:introducedbills": {
            "simple": True,
            "title": "New Bills and Resolutions",
            "slug": "introduced-bills",
            "simple": True,
            "single_event_type": True,
            "sort_order": 106,
            "category": "federal-bills",
            "description": "Get an update whenever a new bill or resolution is introduced.",
        },
        "misc:activebills2": {
            "simple": True,
            "title": "Major Legislative Activity",
            "slug": "major-bill-activity",
            "simple": True,
            "sort_order": 100,
            "category": "federal-bills",
            "description": "Get an update when any bill is scheduled for debate or has major action such as a vote or being enacted.",
        },
        "misc:comingup": {
            "simple": True,
            "title": "Legislation Coming Up",
            "slug": "coming-up",
            "simple": True,
            "single_event_type": True,
            "sort_order": 102,
            "category": "federal-bills",
            "description": "You will get updates when any bill is scheduled for debate in the week ahead by the House Majority Leader or in the day ahead according to the Senate Floor Schedule.",
        },
        "misc:allcommittee": {
            "simple": True,
            "title": "Committee Meetings",
            "link": "/congress/committees",
            "simple": True,
            "sort_order": 103,
            "category": "federal-committees",
            "description": "Get an alert whenever a committee hearing or mark-up session is scheduled.",
        },
        "misc:allvotes": {
            "simple": True,
            "title": "Roll Call Votes",
            "link": "/congress/votes",
            "simple": True,
            "single_event_type": True,
            "sort_order": 101,
            "category": "federal-votes",
            "description": "You will get an alert for every roll call vote in Congress.",
        },
        "bill:": {
            "title": lambda self : truncate_words(self.bill().title, 12),
            "noun": "bill",
            "link": lambda self: self.bill().get_absolute_url(),
            "category": "federal-bills",
            "description": "You will get updates when this bill is scheduled for debate, has a major action such as a vote, or gets a new cosponsor, when a committee meeting is scheduled, when bill text becomes available or when we write a bill summary, plus similar events for related bills.",
        },
        "p:": {
            "title": lambda self : self.person().name,
            "noun": "person",
            "includes": lambda self : [self.person().get_feed("pv"), self.person().get_feed("ps")],
            "link": lambda self: self.person().get_absolute_url(),
            "scoped_title": lambda self : "All Events for " + self.person().lastname,
            "category": "federal-other",
            "description": "You will get updates about major activity on sponsored bills and how this Member of Congress votes in roll call votes.",
        },
        "ps:": {
            "title": lambda self : self.person().name + " - Bills Sponsored",
            "noun": "person",
            "link": lambda self: self.person().get_absolute_url(),
            "scoped_title": lambda self : self.person().lastname + "'s Sponsored Bills",
            "category": "federal-bills",
            "description": "You will get updates about major activity on bills sponsored by this Member of Congress.",
        },
        "pv:": {
            "title": lambda self : self.person().name + " - Voting Record",
            "noun": "person",
            "link": lambda self: self.person().get_absolute_url(),
            "scoped_title": lambda self : self.person().lastname + "'s Voting Record",
            "single_event_type": True,
            "category": "federal-votes",
            "description": "You will get updates on how this Member of Congress votes in roll call votes.",
        },
        "committee:": {
            "title": lambda self : truncate_words(self.committee().fullname, 12),
            "noun": "committee",
            "includes": lambda self : [self.committee().get_feed("bills"), self.committee().get_feed("meetings")],
            "link": lambda self: self.committee().get_absolute_url(),
            "scoped_title": lambda self : "All Events for This Committee",
            "is_valid": lambda self : self.committee(test=True),
            "category": "federal-committees",
            "description": "You will get updates about major activity on bills referred to this commmittee plus notices of scheduled hearings and mark-up sessions.",
        },
        "committeebills:": {
            "title": lambda self : "Bills in " + truncate_words(self.committee().fullname, 12),
            "noun": "committee",
            "link": lambda self: self.committee().get_absolute_url(),
            "scoped_title": lambda self : "Activity on This Committee's Bills",
            "category": "federal-committees",
            "description": "You will get updates about major activity on bills referred to this commmittee.",
        },
        "committeemeetings:": {
            "title": lambda self : "Meetings for " + truncate_words(self.committee().fullname, 12),
            "noun": "committee",
            "link": lambda self: self.committee().get_absolute_url(),
            "scoped_title": lambda self : "This Committee's Hearings and Markups",
            "single_event_type": True,
            "category": "federal-committees",
            "description": "You will get notices for this committee's scheduled hearings and mark-up sessions.",
        },
        "crs:": {
            "title": lambda self : self.issue().name,
            "noun": "subject area",
            "link": lambda self: self.issue().get_absolute_url(),
            "is_valid": lambda self : self.issue(test=True),
            "category": "federal-bills",
            "description": "You will get updates about major activity on bills in this subject area including notices of newly introduced bills, updates when a bill is scheduled for debate, has a major action such as a vote, or gets a new cosponsor, when bill text becomes available or when we write a bill summary.",
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
              
              simple = True
                       Whether this feed's name is exactly the prefix as given (i.e.
                       it has no internal arguments) and should be included in any
                       list of suggested simple trackers.
                       
               includes = function
                        A function from the feed object to an iterable of Feed objects
                        that should also be queried for the events in this feed instead.
                       
               meta = True
                       Set to True if no events are stored in the database for this
                       feeed. It may have an 'includes' to slurp in other feeeds.
                       
               single_event_type = True
                        Set to True if the feed only has events of a single type.
        """
        Feed.feed_metadata[prefix] = metadata
     
        
    def type_metadata(self):
        if self.feedname in Feed.feed_metadata:
            return Feed.feed_metadata[self.feedname]
        if ":" in self.feedname:
            t = self.feedname.split(":")[0]
            if t+":" in Feed.feed_metadata:
                return Feed.feed_metadata[t+":"]
        return None
        
    # constructors for feeds

    @staticmethod # private method
    def get_noarg_feed(feedname):
        feed, is_new = Feed.objects.get_or_create(feedname=feedname)
        return feed

    # iterator methods
    
    @staticmethod
    def get_simple_feeds():
        ret = []
        for fname, fmeta in Feed.feed_metadata.items():
            if fmeta.get("simple", False) == True:
                ret.append((fmeta.get("sort_order", 99999), Feed.objects.get_or_create(feedname=fname)[0]))
        ret.sort(key = lambda x : x[0])
        return [r[1] for r in ret]
    
    # accessor methods
    
    @property
    def isvalid(self):
        m = self.type_metadata()
        if m == None: return False
        if "is_valid" not in m: return True
        return m["is_valid"](self)
    
    @property
    def title(self):
        m = self.type_metadata()
        if "title" not in m: return unicode(self)
        if callable(m["title"]):
            return m["title"](self)
        return m["title"]
        
    @property
    def scoped_title(self):
        m = self.type_metadata()
        if "scoped_title" not in m: return self.title
        if callable(m["scoped_title"]):
            return m["scoped_title"](self)
        return m["scoped_title"]
        
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
        
    @property
    def single_event_type(self):
        m = self.type_metadata()
        return m.get("single_event_type", False)

    @property
    def category(self):
        m = self.type_metadata()
        return m.get("category", None)
    @property
    def description(self):
        m = self.type_metadata()
        return m.get("description", None)

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
         
    def committee(self, test=False):
         if not hasattr(self, "_ref"):
               if ":" in self.feedname and self.feedname.split(":")[0] in ("committee", "committeebills", "committeemeetings"):
                    import committee.models
                    try:
                        return committee.models.Committee.objects.get(code=self.feedname.split(":")[1])
                    except:
                        if test: return False
                        raise
               else:
                    self._ref = None
         return self._ref
         
    def issue(self, test=False):
         if not hasattr(self, "_ref"):
               if ":" in self.feedname and self.feedname.split(":")[0] in ("crs",):
                   import bill.models
                   try:
                       return bill.models.BillTerm.objects.get(id=self.feedname.split(":")[1])
                   except:
                       # For legacy calls to RSS feeds, try to map subject name to object.
                       # Many subject names have changed, so this is the best we can do.
                       # Only test against new-style subject terms since we don't generate
                       # events for old bills with old subject terms.
                       try:
                           return bill.models.BillTerm.objects.get(name=self.feedname.split(":")[1], term_type=bill.models.TermType.new)
                       except bill.models.BillTerm.DoesNotExist:
                           if test: return False
                           raise
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
    the source object (self) and adds a single event to multiple feeds. Note that Event.update() will
    clear out any previously created events for the source object if they are not re-added here.
        from events.models import Event
        with Event.update(self) as E:
            E.add("eventcode", self.created, feedinstance1)
            E.add("eventcode", self.created, feedinstance2)
                
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
             ('when', 'source_content_type', 'source_object_id', 'seq', 'feed'))
    
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
            #print ("[%s] %s event record: %s | %s | %s" % (unicode(self.source)[0:15], "New" if created else "Existing", feed.feedname, repr(self.source), eventid)).encode("utf8")
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
    trackers = models.ManyToManyField(Feed, related_name="tracked_in_lists")
    is_default = models.BooleanField(default=False)
    email = models.IntegerField(default=0, choices=EMAIL_CHOICES)
    last_event_mailed = models.IntegerField(blank=True, null=True) # id of last event
    last_email_sent = models.DateTimeField(blank=True, null=True) # date of last email update sent
    public_id = models.CharField(max_length=16, blank=True, null=True, db_index=True)
    
    class Meta:
        unique_together = [('user', 'name')]
        
    @staticmethod
    def create(user, email_rate=None):
        sublist = None
        ctr = 1
        base_name = "My List"
        if email_rate == 1: base_name = "Daily Updates"
        if email_rate == 2: base_name = "Weekly Updates"
        while not sublist and ctr < 1000:
            try:
                sublist = SubscriptionList.objects.create(user=user, name=base_name + (" " + str(ctr) if ctr > 1 else ""))
            except:
                ctr += 1
        if email_rate != None:
            sublist.email = email_rate
        return sublist

    @staticmethod
    def get_for_email_rate(user, email_rate):
        try:
            sublist = SubscriptionList.objects.get(user=user, is_default=True)
            if sublist.email == email_rate:
                return sublist
                
            if sublist.trackers.count() == 0:
                # The default list has a different email rate set, but it's
                # empty so just revise it.
                sublist.email = email_rate
                sublist.save()

                # Also try to rename it, but be careful of the uniqueness
                # constraint on the name.
                try:
                    if sublist.email == 0:
                        sublist.name = "My List"
                    elif sublist.email == 1:
                        sublist.name = "Daily Email Updates"
                    elif sublist.email == 2:
                        sublist.name = "Weekly Email Updates"
                    sublist.save()
                except:
                    pass # uniqueness constraint on name violated, doesn't matter
                return sublist
            else:
                # The default list has something in it at a different email rate,
                # so fall back.
                raise SubscriptionList.DoesNotExist()                    
        except SubscriptionList.DoesNotExist:
            try:
                # If there is a single list with the desired email rate, use that list.
                return SubscriptionList.objects.get(user=user, email=email_rate)
            except SubscriptionList.DoesNotExist:
                # There is no list with the desired email rate, so create a new list.
                return SubscriptionList.create(user, email_rate=email_rate)

    def get_public_id(self):
        if not self.public_id:
            from random import choice
            import string
            self.public_id = ''.join([choice(string.letters + string.digits) for i in range(16)])
            self.save()
        return self.public_id

    def get_new_events(self):
        feeds, source_feed_map = expand_feeds(self.trackers.all())
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
        feedmap = dict((f.id, source_feed_map.get(f, f)) for f in feeds)
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
    map_to_source = { }
    i = 0
    while i < len(feeds):
        for f in feeds[i].includes_feeds():
            if f not in feeds: # don't include a feed already included, and don't add a mapping for it in map_to_source
                map_to_source[f] = feeds[i]
                feeds.append(f)
        i += 1
    return feeds, map_to_source

def truncate_words(s, num):
    from django.utils.text import Truncator
    return Truncator(s).words(num, truncate=" ...")
    

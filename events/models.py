# -*- coding: utf-8 -*-
from django.db import models
from django.core.urlresolvers import reverse
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic

class Feed(models.Model):
    """Maps feed names to integer keys used in the Event model."""
    feedname = models.CharField(max_length=64, unique=True, db_index=True)

    def __unicode__(self):
        return self.feedname
        
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
                
            self.feed_cache = {}
            
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
            
            # Convert the feeds.Feed object feed into a models.Feed fieldrec.
            if feed in self.feed_cache:
                feedrec = self.feed_cache[feed]
            else:
                feedrec, created = Feed.objects.get_or_create(feedname=feed.getname())
                self.feed_cache[feed] = feedrec
            
            # Create the record for this event for this feed, if it does not exist.
            event, created = Event.objects.get_or_create(
                feed = feedrec,
                eventid = eventid,
                defaults = {"id": self.next_id, "when": when},
                **Event.sourcearg(self.source)
                )
            if created:
                self.next_id += 1
            else:
                del self.existing_events[event.id] # i.e. don't delete this event on __exit__
                if event.when != when: # update this if it changed
                    event.when = when
                    event.save()
            
        def __exit__(self, type, value, traceback):
            # Clear out any events that were not updated.
            Event.objects.filter(id__in=self.existing_events).delete()
            return False


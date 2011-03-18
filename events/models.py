# -*- coding: utf-8 -*-
from django.db import models
from django.core.urlresolvers import reverse
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic

from picklefield import PickledObjectField

from common import enum

class Feed(models.Model):
    feedclass = PickledObjectField()

    def __unicode__(self):
        return unicode(self.feedclass)
        
class Event(models.Model):
    """
    Holds info about an event in a feed. The primary key is used as a monotonically
    increasing sequence number for all records.
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
            # Convert the feeds.Feed object feed into a models.Feed fieldrec.
            if feed in self.feed_cache:
                feedrec = self.feed_cache[feed]
            else:
                feedrec, created = Feed.objects.get_or_create(feedclass=feed)
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
            Event.objects.filter(id__in=self.existing_events).delete()
            return False


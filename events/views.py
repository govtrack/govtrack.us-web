# -*- coding: utf-8 -*-
from django.shortcuts import redirect, get_object_or_404
from django.core.urlresolvers import reverse
from django.http import HttpResponse

from common.decorators import render_to
from common.pagination import paginate

from datetime import datetime, time
import simplejson

import feeds
from models import *
from events.templatetags.events_utils import render_event

def get_feed_list(request):
    feedlist = request.GET.get('feeds', '').split(',')
    if feedlist == [""]:
        feedlist = []
    else:
        feedlist = [feeds.Feed.from_name(f) for f in feedlist]
    return feedlist

@render_to('events/events_list.html')
def events_list(request):
    feedlist = get_feed_list(request)
    feedlistnames = [f.getname() for f in feedlist]
        
    qs = feeds.Feed.get_events_for(feedlist if len(feedlist) > 0 else None).filter(when__lte=datetime.now()) # get all events
    page = paginate(qs, request, per_page=50)
    
    no_arg_feeds = [feeds.ActiveBillsFeed(), feeds.IntroducedBillsFeed(), feeds.ActiveBillsExceptIntroductionsFeed(), feeds.EnactedBillsFeed(), feeds.AllVotesFeed(), feeds.AllCommitteesFeed()]
    no_arg_feeds = [(feed, feed.getname() in feedlistnames) for feed in no_arg_feeds]
        
    return {
        'page': page,
        'no_arg_feeds': no_arg_feeds,
        'feeds': feedlist,
        'feeds_json': simplejson.dumps(feedlistnames),
            }

def search_feeds(request):
    if request.POST["type"] == "person":
        from person.models import Person
        feedlist = [
            feeds.PersonFeed(p.id)
            for p in Person.objects.filter(lastname__contains=request.POST["q"])
            if p.get_current_role() != None]
            
        import us
        for s in us.statenames:
            if us.statenames[s].lower().startswith(request.POST["q"].lower()):
                print s, us.statenames[s]
                feedlist.extend([
                    feeds.PersonFeed(p)
                    for p in Person.objects.filter(roles__current=True, roles__state=s)])
                
    if request.POST["type"] == "committee":
        from committee.models import Committee
        feedlist = [
            feeds.CommitteeFeed(c)
            for c in Committee.objects.filter(name__contains=request.POST["q"], obsolete=False)]
                
    def feedinfo(f):
        return { "name": f.getname(), "title": f.gettitle() }
    return HttpResponse(simplejson.dumps({
        "status": "success",
        "feeds": [feedinfo(f) for f in feedlist],
        }), mimetype="text/json")
   
def events_rss(request):
    import django.contrib.syndication.views
    
    feedlist = get_feed_list(request)
    
    class DjangoFeed(django.contrib.syndication.views.Feed):
        title = ", ".join(f.gettitle() for f in feedlist) + " - Tracked Events from GovTrack.us"
        link = "/"
        description = "GovTrack tracks the activities of the United States Congress."
        
        def items(self):
            return [render_event(item, feedlist) for item in feeds.Feed.get_events_for(feedlist)[0:20]]
            
        def item_title(self, item):
            return item["title"]
        def item_description(self, item):
            return item["body_text"]
        def item_link(self, item):
            return item["url"] 
        def item_guid(self, item):
            return "http://www.govtrack.us/events/guid/" + item["guid"] 
        def item_pubdate(self, item):
            return item["date"] if isinstance(item["date"], datetime) else datetime.combine(item["date"], time.min)
            
    return DjangoFeed()(request)
    
            

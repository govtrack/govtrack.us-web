# -*- coding: utf-8 -*-
from django.shortcuts import redirect, get_object_or_404
from django.core.urlresolvers import reverse
from django.http import HttpResponse

from common.decorators import render_to
from common.pagination import paginate

from datetime import datetime, time
import simplejson

from models import *
from website.models import *
from events.templatetags.events_utils import render_event

def get_feed_list(request):
    feedlist = request.GET.get('feeds', '').split(',')
    if feedlist == [""]:
        feedlist = []
    else:
        feedlist = [Feed.from_name(f) for f in feedlist]
    return feedlist

@render_to('events/events_list.html')
def events_list(request):
    if not request.user.is_authenticated():
        feedlist = get_feed_list(request)
    else:
        feedlist = [] # ignore query string if user is logged in
    feedlistnames = [f.feedname for f in feedlist]
        
    no_arg_feeds = [Feed.ActiveBillsFeed(), Feed.IntroducedBillsFeed(), Feed.ActiveBillsExceptIntroductionsFeed(), Feed.EnactedBillsFeed(), Feed.AllVotesFeed(), Feed.AllCommitteesFeed()]
    no_arg_feeds = [(feed, feed.feedname in feedlistnames) for feed in no_arg_feeds]
        
    return {
        'no_arg_feeds': no_arg_feeds,
        'feeds': feedlist,
        'feeds_json': simplejson.dumps(feedlistnames),
            }

@render_to('events/events_list_items.html')
def events_list_items(request):
    sublist = None
    show_empty = True
    newlist = False
    if "listid" not in request.GET:
        feedlist = get_feed_list(request)
    elif not request.user.is_authenticated():
        return {} # invalid call
    elif request.GET["listid"] == "_new_list" and request.GET["command"] not in ("toggle", "add"):
        feedlist = []
        show_empty = False
    else:
        if request.GET["listid"] != "_new_list":
            sublist = get_object_or_404(SubscriptionList, user=request.user, id=request.GET["listid"])
        else:
            sublist = SubscriptionList.objects.create(user=request.user, name="New List " + datetime.now().isoformat()) # make new name such that it will always be unique!
            newlist = True
        
        if request.GET["command"] in ("toggle", "add"):
            f = get_object_or_404(Feed, feedname=request.GET["command_arg"])
            if f in sublist.trackers.all() and request.GET["command"] == "toggle":
                sublist.trackers.remove(f)
            else:
                sublist.trackers.add(f)
        if request.GET["command"] == "rename":
            sublist.name = request.GET["command_arg"]
            sublist.save()
            return { } # response is ignored
        if request.GET["command"] == "delete" and not sublist.is_default:
            sublist.delete()
            return { } # response is ignored
        
        feedlist = sublist.trackers.all()
        show_empty = False
      
    if len(feedlist) > 0 or show_empty:
        qs = Feed.get_events_for(feedlist if len(feedlist) > 0 else None).filter(when__lte=datetime.now()) # get all events
    else:
        qs = []
    page = paginate(qs, request, per_page=50)
    
    return {
        'page': page,
        'list': sublist,
        'feeds': feedlist,
        'newlist': newlist,
            }

def search_feeds(request):
    if request.POST["type"] == "person":
        from person.models import Person
        feedlist = [
            Feed.PersonFeed(p.id)
            for p in Person.objects.filter(lastname__contains=request.POST["q"])
            if p.get_current_role() != None]
            
        import us
        for s in us.statenames:
            if us.statenames[s].lower().startswith(request.POST["q"].lower()):
                print s, us.statenames[s]
                feedlist.extend([
                    Feed.PersonFeed(p)
                    for p in Person.objects.filter(roles__current=True, roles__state=s)])
                
    if request.POST["type"] == "committee":
        from committee.models import Committee
        feedlist = [
            Feed.CommitteeFeed(c)
            for c in Committee.objects.filter(name__contains=request.POST["q"], obsolete=False)]
                
    def feedinfo(f):
        return { "name": f.feedname, "title": f.title }
    return HttpResponse(simplejson.dumps({
        "status": "success",
        "feeds": [feedinfo(f) for f in feedlist],
        }), mimetype="text/json")
   
def events_rss(request):
    import django.contrib.syndication.views
    
    feedlist = get_feed_list(request)
    
    class DjangoFeed(django.contrib.syndication.views.Feed):
        title = ", ".join(f.title for f in feedlist) + " - Tracked Events from GovTrack.us"
        link = "/"
        description = "GovTrack tracks the activities of the United States Congress."
        
        def items(self):
            return [render_event(item, feedlist) for item in Feed.get_events_for(feedlist)[0:20]]
            
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
    
            

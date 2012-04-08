# -*- coding: utf-8 -*-
from django.shortcuts import redirect, get_object_or_404
from django.core.urlresolvers import reverse
from django.http import HttpResponse, Http404
from django.contrib.auth.decorators import login_required

from common.decorators import render_to
from common.pagination import paginate

from datetime import datetime, time
import simplejson

from registration.helpers import json_response

from models import *
from website.models import *
from events.templatetags.events_utils import render_event
from settings import CURRENT_CONGRESS

def get_feed_list(request):
    feedlist = request.GET.get('feeds', '').split(',')
    if feedlist == [""]:
        feedlist = []
    else:
        feedlist = [Feed.from_name(f) for f in feedlist]
    return feedlist

@login_required
@render_to('events/edit_lists.html')
def edit_subscription_lists(request):
    no_arg_feeds = [Feed.IntroducedBillsFeed(), Feed.EnactedBillsFeed(), Feed.ActiveBillsFeed(),  Feed.ActiveBillsExceptIntroductionsFeed(), Feed.ComingUpFeed(), Feed.AllVotesFeed(), Feed.AllCommitteesFeed()]
    
    from bill.search import subject_choices
    
    return {
        'no_arg_feeds': no_arg_feeds,
        'subject_choices': subject_choices(),
            }
            
@login_required
@json_response
def edit_subscription_list(request):
    if not request.user.is_authenticated():
        return { "error": "not logged in" }
        
    if request.POST["listid"] != "_new_list":
        sublist = get_object_or_404(SubscriptionList, user=request.user, id=request.POST["listid"])
    else:
        sublist = None
        ctr = 1
        while not sublist and ctr < 1000:
            try:
                sublist = SubscriptionList.objects.create(user=request.user, name="New List " + str(ctr))
            except:
                ctr += 1
    
    state = None
    
    if request.POST["command"] in ("toggle", "add", "remove"):
        f = get_object_or_404(Feed, feedname=request.POST["feed"])
        if (request.POST["command"] == "toggle" and f in sublist.trackers.all()) or request.POST["command"] == "remove":
            sublist.trackers.remove(f)
            state = False
        else:
            sublist.trackers.add(f)
            state = True
    if request.POST["command"] == "rename":
        sublist.name = request.POST["name"]
        sublist.save()
    if request.POST["command"] == "delete" and not sublist.is_default:
        sublist.delete()
    if request.POST["command"] == "email_toggle":
        sublist.email = (sublist.email + 1) % len(SubscriptionList.EMAIL_CHOICES)
        sublist.save()
    
    return { "list_id": sublist.id, "list_name": sublist.name, "list_email": sublist.get_email_display(), "list_trackers": [ { "id": f.id, "name": f.feedname, "title": f.title, "link": f.link } for f in sublist.trackers.all() ], "state": state }

@render_to('events/events_list_items.html')
def events_list_items(request):
    sublist = get_object_or_404(SubscriptionList, user=request.user, id=request.POST["listid"])
        
    feedlist = sublist.trackers.all()
    show_empty = False
      
    if len(feedlist) > 0 or show_empty:
        qs = Feed.get_events_for(feedlist if len(feedlist) > 0 else None, 100) # get all events
    else:
        qs = []
    page = paginate(qs, request, per_page=50)
    
    return {
        'page': page,
        'list': sublist,
        'feeds': feedlist,
            }

def search_feeds(request):
    if request.REQUEST["type"] == "person":
        from person.models import Person
        feedlist = [
            Feed.PersonFeed(p.id)
            for p in Person.objects.filter(lastname__icontains=request.REQUEST["q"])
            if p.get_current_role() != None]
            
        import us
        for s in us.statenames:
            if us.statenames[s].lower().startswith(request.REQUEST["q"].lower()):
                feedlist.extend([
                    Feed.PersonFeed(p)
                    for p in Person.objects.filter(roles__current=True, roles__state=s)])
                
    if request.REQUEST["type"] == "bill":
        from haystack.query import SearchQuerySet
        feedlist = [
            Feed.BillFeed(b.object)
            for b in SearchQuerySet().filter(indexed_model_name__in=["Bill"], congress__in=[CURRENT_CONGRESS], content=request.REQUEST["q"])[0:10]]
    
    if request.REQUEST["type"] == "committee":
        from committee.models import Committee
        feedlist = [
            Feed.CommitteeFeed(c)
            for c in Committee.objects.filter(name__icontains=request.REQUEST["q"], obsolete=False).order_by("committee__name", "name")[0:10]]
                
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
            events = [render_event(item, feedlist) for item in Feed.get_events_for(feedlist, 20)]
            return [e for e in events if e != None]
            
        def item_title(self, item):
            return item["title"]
        def item_description(self, item):
            return item["body_text"]
        def item_link(self, item):
            return "http://www.govtrack.us" + item["url"] 
        def item_guid(self, item):
            return "http://www.govtrack.us/events/guid/" + item["guid"] 
        def item_pubdate(self, item):
            return item["date"] if isinstance(item["date"], datetime) else datetime.combine(item["date"], time.min)
            
    return DjangoFeed()(request)
    
@render_to('events/showfeed.html')
def events_show_feed(request, feedslug):
    # Map slug to feed internal name, then Feed object.
    for feedname, feedmeta in Feed.feed_metadata.items():
        if feedmeta.get("slug", "") == feedslug:
            feed = Feed.from_name(feedname)
            break
    else:
        raise Http404()
        
    return {
        "feed": feed,
        "meta":  feedmeta,
    }


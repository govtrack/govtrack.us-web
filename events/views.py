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
    if "list_id" in request.GET:
        lst = get_object_or_404(SubscriptionList, public_id=request.GET["list_id"])
        return lst.trackers.all(), lst.user.username + "'s " + lst.name
    else:
        feedlist = request.GET.get('feeds', '').split(',')
        if feedlist == [""]:
            feedlist = []
            feedtitle = "Tracked Events from GovTrack.us (All Events)"
        else:
            feedlist2 = []
            for f in feedlist:
                try:
                    feedlist2.append(Feed.from_name(f))
                except Feed.DoesNotExist:
                    f = Feed(feedname=f)
                    if not f.isvalid: raise Http404("Invalid feed name.")
                    feedlist2.append(f)
            feedlist = feedlist2
            feedtitle = ", ".join(f.title for f in feedlist) + " - Tracked Events from GovTrack.us"
        return feedlist, feedtitle

@login_required
@render_to('events/edit_lists.html')
def edit_subscription_lists(request):
    return {
        'no_arg_feeds': Feed.get_simple_feeds(),
            }
            
@login_required
@json_response
def edit_subscription_list(request):
    if not request.user.is_authenticated():
        return { "error": "not logged in" }
        
    if not "listid" in request.POST:
        return { "error": "missing parameter" }
    elif request.POST["listid"] != "_new_list":
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
    if request.POST["command"] == "set_email_frequency":
        sublist.email = int(request.POST["value"])
        sublist.save()
    
    return {
        "list_id": sublist.id,
        "list_name": sublist.name,
        "list_public_id": sublist.get_public_id(),
        "list_email": sublist.email,
        "list_email_display": sublist.get_email_display(),
        "list_trackers": [
            { "id": f.id, "name": f.feedname, "title": f.title, "link": f.link }
            for f in sublist.trackers.all() ], "state": state }

@render_to('events/events_list_items.html')
def events_list_items(request):
    if "listid" in request.POST:
        sublist = get_object_or_404(SubscriptionList, user=request.user, id=request.POST["listid"])
        feedlist = sublist.trackers.all()
        show_empty = False
    elif "feed" in request.POST:
        sublist = None
        feedlist = [Feed.from_name(request.POST["feed"], must_exist=False)]
        show_empty = True
    else:
        raise Http404()
        
    if len(feedlist) > 0 or show_empty:
        qs = Feed.get_events_for(feedlist if len(feedlist) > 0 else None, 100) # get all events
    else:
        qs = []
    page = paginate(qs, request, per_page=50)
    
    # Based on the last 100 events, how often do we expect to get email updates?
    # Compute this using the median time between events, which should give us an
    # idea of how often the events occur in a way that is robust to a few long
    # periods of no events, e.g. which Congress is out of session.
    expected_frequency = None
    if len(qs) > 15:
        # Get the time between consecutive events, in days.
        seps = []
        for i in xrange(1, len(qs)):
            s = (qs[i-1]["when"]-qs[i]["when"]).total_seconds()
            if s == 0: continue # skip things that happen at exactly the same time,
                                # since they probably don't help us understand frequency
            seps.append( s/float(60*60*24) )
        
        # Find the median.
        if len(seps) == 0:
            # everything occurred at the same moment
            days_between_events = 1000
        else:
            seps.sort()
            days_between_events = seps[len(seps)/2]
        
        if not sublist or sublist.email == 0:
            if days_between_events < 1:
                expected_frequency = "Turn on daily email updates if you would like to get these events sent to you each day."
            elif days_between_events < 7:
                expected_frequency = "Turn on daily or weekly email updates if you would like to get these events mailed to you each day or week."
        elif sublist.email == 1:
            if days_between_events < 1:
                expected_frequency = "You can expect an email update roughly every day Congress is in session."
            elif days_between_events < 4:
                expected_frequency = "You can expect an email update every couple of days."
            elif days_between_events < 6:
                expected_frequency = "You can expect an email update every week."
            else:
                expected_frequency = "You will get email updates when more events in Congress occur matching the items you are tracking."
        elif sublist.email == 2:
            if days_between_events < 6:
                expected_frequency = "You can expect an email update every week."
            elif days_between_events < 20:
                expected_frequency = "You can expect an email update every couple of weeks."
            else:
                expected_frequency = "You will get email updates when more events in Congress occur matching the items you are tracking."

    return {
        'page': page,
        'list': sublist,
        'feeds': feedlist,
        'expected_frequency': expected_frequency,
            }
            
def events_rss(request):
    import django.contrib.syndication.views
    import urllib
    
    feedlist, feedtitle = get_feed_list(request)
    
    class DjangoFeed(django.contrib.syndication.views.Feed):
        title = feedtitle
        link = "/" if len(feedlist) != 1 else feedlist[0].link
        description = "GovTrack tracks the activities of the United States Congress."
        
        def items(self):
            events = [render_event(item, feedlist) for item in Feed.get_events_for(feedlist, 20)]
            return [e for e in events if e != None]
            
        def item_title(self, item):
            return item["title"]
        def item_description(self, item):
            return item["type"] + ": " + item["body_text"]
        def item_link(self, item):
            return "http://www.govtrack.us" + item["url"] + "?utm_campaign=govtrack_feed&utm_source=govtrack/feed&utm_medium=rss"
        def item_guid(self, item):
            return self.item_link(item) + "#eventid=" + urllib.quote_plus(item["guid"]) 
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

@render_to('events/add_tracker.html')
def events_add_tracker(request):
    return {
        'no_arg_feeds': Feed.get_simple_feeds(),
    }
    
@json_response
def start_search(request):
    # Do a site search to find relevant trackers.
    
    from website.views import do_site_search
    ret = []
    for grp in do_site_search(request.GET.get("q", "")):
        feeds = [{
            "name": r["feed"].feedname,
            "title": r["label"],
            "subfeeds": [{
                    "name": f.feedname,
                    "title": f.scoped_title,
                }
                for f in r["feed"].includes_feeds()],
            }
            for r in grp["results"] if "feed" in r]
        ret.append({
            "title": grp["title"],
            "href": grp["href"],
            "qsarg": grp.get("qsarg", None),
            "feeds": feeds
        })
    return ret
    

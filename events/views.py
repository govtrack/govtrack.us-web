# -*- coding: utf-8 -*-
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.http import HttpResponse, Http404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings
from django.core.paginator import Paginator

from common.decorators import render_to

from datetime import datetime, time

from registration.helpers import json_response
from twostream.decorators import anonymous_view

from .models import *
from website.models import *
from events.templatetags.events_utils import render_event

def get_feed_list(request):
    if "list_id" in request.GET:
        lst = get_object_or_404(SubscriptionList, public_id=request.GET["list_id"])
        return lst.trackers.all(), lst.user.username + "'s " + lst.name
    else:
        # monitors was the old URL parameter, used by events_embed_legacy
        feedlist = request.GET.get('feeds', request.GET.get('monitors', '')).split(',')
        if feedlist == [""]:
            feedlist = []
            feedtitle = "All Events"
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
            feedtitle = ", ".join(f.title for f in feedlist)
        return feedlist, feedtitle

@login_required
@render_to('events/edit_lists.html')
def edit_subscription_lists(request):
    message = None
    sublist = None
    
    if "add" in request.GET:
        # This is a redirect from the add tracker page.

        # Get the list to add the feed into
        if "emailupdates" in request.GET:
            email_rate = int(request.GET["emailupdates"])
            sublist = SubscriptionList.get_for_email_rate(request.user, email_rate)    
        else:
            sublist = request.user.userprofile().lists().get(id=request.GET["listid"])

        feed = Feed.from_name(request.GET["add"])
        # for 'meta' feeds like bill search, we may get back a feed not in the db
        if not feed.id: feed.save()
        
        if not feed in sublist.trackers.all(): sublist.trackers.add(feed)
        sublist.save()
        
        if request.user.userprofile().lists().count() <= 1:
            message = "You are now tracking " + feed.title + "."
        else:
            message = feed.title + " was added to your list " + sublist.name + "."
    
    return {
        'default_list': sublist,
        'message': message,
        'no_arg_feeds': Feed.get_simple_feeds(),
            }
            
@login_required
@json_response
def edit_subscription_list(request):
    if not request.user.is_authenticated:
        return { "error": "not logged in" }
        
    if "email_freq" in request.POST:
        # Use the default list, unless a different email update rate is chosen.
        email_rate = int(request.POST["email_freq"])
        sublist = SubscriptionList.get_for_email_rate(request.user, email_rate)
        
    elif not "listid" in request.POST:
        if request.POST["command"] != "remove-from-all":
            return { "error": "missing parameter" }
    elif request.POST["listid"] != "_new_list":
        sublist = get_object_or_404(SubscriptionList, user=request.user, id=request.POST["listid"])
    else:
        sublist = SubscriptionList.create(request.user)
    
    state = None
    
    if request.POST["command"] in ("toggle", "add", "remove"):
        f = get_object_or_404(Feed, feedname=request.POST["feed"])
        
        if "email_freq" in request.POST:
            # Delete the tracker from all other lists.
            for s in SubscriptionList.objects.filter(user=request.user):
                s.trackers.remove(f)
                if not s.is_default and s.trackers.count() == 0: s.delete()
        
        if (request.POST["command"] == "toggle" and f in sublist.trackers.all()) or request.POST["command"] == "remove":
            sublist.trackers.remove(f)
            state = False
        else:
            try:
                sublist.trackers.add(f)
            except:
                # Ignore any uniqueness constraint violation.
                pass
            state = True
    if request.POST["command"] == "remove-from-all":
        f = get_object_or_404(Feed, feedname=request.POST["feed"])
        for s in SubscriptionList.objects.filter(user=request.user):
            s.trackers.remove(f)
            if not s.is_default and s.trackers.count() == 0: s.delete()
        return { "status": "OK" }
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
            for f in sublist.trackers.all() ],
        "state": state }

@render_to('events/events_list_items.html')
def events_list_items(request):
    if "listid" in request.POST:
        sublist = get_object_or_404(SubscriptionList, user=request.user, id=request.POST["listid"])
        feedlist = sublist.trackers.all()
        show_empty = False
    elif "feed" in request.POST:
        sublist = None
        try:
            feedlist = [Feed.from_name(request.POST["feed"])]
            show_empty = True
        except Feed.DoesNotExist:
            feedlist = []
            show_empty = False
    else:
        raise Http404()
        
    if len(feedlist) > 0 or show_empty:
        try:
            count = int(request.POST.get('count', '100'))
        except:
            raise Http404()
        qs = Feed.get_events_for(feedlist if len(feedlist) > 0 else None, count) # get all events
    else:
        qs = []
    page = Paginator(qs, 50)
    
    # Based on the last 100 events, how often do we expect to get email updates?
    # Compute this using the median time between events, which should give us an
    # idea of how often the events occur in a way that is robust to a few long
    # periods of no events, e.g. which Congress is out of session.
    expected_frequency = None
    if len(qs) > 15:
        # Get the time between consecutive events, in days.
        seps = []
        for i in range(1, len(qs)):
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
            days_between_events = seps[len(seps)//2]
        
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
        'simple_mode': len(feedlist) == 1 and feedlist[0].single_event_type,
            }

@anonymous_view            
def events_rss(request):
    import django.contrib.syndication.views
    import urllib.request, urllib.parse, urllib.error

    try:
        feedlist, feedtitle = get_feed_list(request)
    except Exception as e:
        raise Http404(str(e))
    feedtitle += " - Tracked Events from GovTrack.us"
    
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
            return settings.SITE_ROOT_URL + item["url"] + settings.RSS_CAMPAIGN_QUERYSTRING
        def item_guid(self, item):
            return self.item_link(item) + "#eventid=" + urllib.parse.quote_plus(item["guid"]) 
        def item_pubdate(self, item):
            return item["date"] if (not item["date"] or isinstance(item["date"], datetime)) else datetime.combine(item["date"], time.min)
            
    return DjangoFeed()(request)
    
@render_to('events/showfeed.html')
def events_show_feed(request, feedslug):
    # Map slug to feed internal name, then Feed object.
    for feedname, feedmeta in Feed.feed_metadata.items():
        if feedmeta.get("slug", "") == feedslug:
            feed = Feed.from_name(feedname)
            break
    else:
        if feedslug == "track-something" and "feed" in request.GET:
            try:
                feed = Feed.from_name(request.GET["feed"])
            except:
                raise Http404()
        else:
            raise Http404()
        
    return {
        "feed": feed,
    }

@anonymous_view            
def events_embed_legacy(request):
    # prepare template context
    try:
        feedlist, feedtitle = get_feed_list(request)
    except ObjectDoesNotExist:
        raise Http404()
    except ValueError:
        raise Http404()
    try:
        count = int(request.GET.get('count', ''))
    except ValueError:
        count = 10
    events = Feed.get_events_for(feedlist, count)
    context = { "feeds": feedlist, "events": events, "title": feedtitle,
        "link": feedlist[0].link if len(feedlist) == 1 else None }
        
    # render the HTML
    from django.template import Template, Context, loader
    html = loader.get_template("events/events_embed_legacy.html")\
        .render(context)
    
    # convert to Javascript document.write statements.
    from django.utils.html import strip_spaces_between_tags
    from django.template.defaultfilters import escapejs
    html = strip_spaces_between_tags(html)
    js = ""
    while len(html) > 0:
        js += "document.write(\"" + escapejs(html[0:128]) + "\");\n"
        html = html[128:]
    return HttpResponse(js, content_type="application/x-javascript; charset=UTF-8")
    
@render_to('events/view_list.html')
def view_list(request, list_id):
    # Get all of the trackers in the list.
    from events.templatetags.events_utils import render_event
    sublist = get_object_or_404(SubscriptionList, public_id=list_id)
    feeds = list(sublist.trackers.all())

    # Get all of the user's notes.
    notes = TrackerNote.objects.filter(user=sublist.user, sublist=sublist).select_related('feed')
    notes = { # make a mapping from feed name to note
        note.feed.feedname: note
        for note in notes
    }

    trackers = [
            {
                "feed": f,
                "id": f.id,
                "name": f.feedname,
                "title": f.title,
                "link": f.link or "/events/something/" + f.slug,
                "thumbnail_image_url": f.thumbnail_image_url(),
                "noun": f.type_metadata().get("noun"),
                "description": f.description,
                "is_subscribable": f.is_subscribable,
                "recently": [
                    render_event(event, [f])
                    for event in f.get_events(1)
                ],
                "user_note": notes.get(f.feedname),
            }
            for f in feeds ]
    trackers.sort(key = lambda t : (t["name"].split(":")[0], t["title"]))
    return {
        "list": sublist,
        "list_trackers": trackers,
    }

@login_required
@json_response
def save_list_note(request):
    # Update an existing note, delete an existing note if the text is empty, or
    # create a new note.
    sublist = SubscriptionList.objects.get(id=request.POST['list'], user=request.user)
    feed = Feed.objects.get(id=request.POST['tracker'])
    text = request.POST['text'].strip()
    note_qs = TrackerNote.objects.filter(user=request.user, sublist=sublist, feed=feed)
    if not text:
        # Delete any existing note.
        note_qs.delete()
        return { "deleted": True }
    else:
        note, _ = TrackerNote.objects.get_or_create(user=request.user, sublist=sublist, feed=feed)
        note.text = text
        note.save()
        return { "html": note.as_html() }

# -*- coding: utf-8 -*-
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import redirect, get_object_or_404, render_to_response
from django.template import RequestContext
from django.core.urlresolvers import reverse
from django.core.cache import cache
from django.views.decorators.cache import cache_page

from common.decorators import render_to
from common.pagination import paginate

from cache_utils.decorators import cached

from events.models import Feed
import us

import re
from datetime import datetime, timedelta

@render_to('website/index.html')
def index(request):
    twitter_feed = cache.get("our_twitter_feed")
    if not twitter_feed:
        import twitter
        twitter_api = twitter.Api()
        twitter_feed = twitter_api.GetUserTimeline("govtrack", since_id=0, count=3)
        
        # replace links
        from django.utils.html import conditional_escape
        from django.utils.safestring import mark_safe
        re_url = re.compile(r"(?i)\b((?:[a-z][\w-]+:(?:/{1,3}|[a-z0-9%])|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))")
        for item in twitter_feed:
            item.text = re_url.sub(lambda m : "<a target=\"_blank\" href=\"" + m.group(0) + "\">" + m.group(0) + "</a>", conditional_escape(item.text))
            
        cache.set("our_twitter_feed", twitter_feed, 60*30) # 30 minutes
        
    blog_feed = cache.get("our_blog_feed")
    if not blog_feed:
        blog_feed = get_blog_items()[0:2]
        cache.set("our_blog_feed", blog_feed, 60*30) # 30 min
    
    events_feed = cache.get("frontpage_events_feed")
    if not events_feed:
        events_feed = Feed.get_events_for(("misc:activebills", "misc:allvotes"), 6)
        cache.set("frontpage_events_feed", events_feed, 60*15) # 15 minutes

    return {
        'events': events_feed,
        'tweets': twitter_feed,
        'blog': blog_feed,
        }
          
def staticpage(request, pagename):
    if pagename == "developers": pagename = "developers/index"
    
    ctx = { 'pagename': pagename }
    
    if pagename == "overview":
        from us import statenames
        from states.views import states_with_data
        ctx['states'] = ((s, statenames[s]) for s in states_with_data())
    
    return render_to_response('website/' + pagename + '.html', ctx, RequestContext(request))

def get_blog_items():
    # c/o http://stackoverflow.com/questions/1208916/decoding-html-entities-with-python
    import re
    def _callback(matches):
        id = matches.group(1)
        try:
           return unichr(int(id))
        except:
           return id
    def decode_unicode_references(data):
        return re.sub("&#(\d+)(;|(?=\s))", _callback, data)

    import feedparser
    feed = feedparser.parse("http://www.govtrack.us/blog/atom")

    return [{"link":entry.link, "title":decode_unicode_references(entry.title), "date":datetime(*entry.updated_parsed[0:6]), "content":decode_unicode_references(entry.content[0].value)} for entry in feed["entries"][0:4]]

def congress_home(request):
    return HttpResponseRedirect("/overview")
    
@render_to('website/search.html')
def search(request):
    q = request.REQUEST.get("q", "")
    if q.strip() == "":
        return { "results": [] }
    
    results = []
    
    from haystack.query import SearchQuerySet
    
    results.append(("Members of Congress and Presidents", "/congress/members", "name",
        [{"href": p.object.get_absolute_url(), "label": p.object.name, "obj": p.object, "secondary": p.object.get_current_role() == None } for p in SearchQuerySet().filter(indexed_model_name__in=["Person"], content=q)[0:9]]))
       
    # Skipping states for now because we might want to go to the district maps or to
    # the state's main page for state legislative information.
    #import us
    #results.append(("States", "/congress/members", "most_recent_role_state",
    #    sorted([{"href": "/congress/members/%s" % s, "label": us.statenames[s] }
    #        for s in us.statenames
    #        if us.statenames[s].lower().startswith(q.lower())
    #        ], key=lambda p : p["label"])))
    
    from committee.models import Committee
    results.append(("Committees", "/congress/committees", None,
        sorted([{"href": c.get_absolute_url(), "label": c.fullname, "obj": c }
        for c in Committee.objects.filter(name__contains=q, obsolete=False)]
        , key=lambda c : c["label"])))
       
    from settings import CURRENT_CONGRESS
    from bill.search import parse_bill_number
    bill = parse_bill_number(q)
    if not bill:
        bills = \
            [{"href": b.object.get_absolute_url(), "label": b.object.title, "obj": b.object, "secondary": b.object.congress != CURRENT_CONGRESS } for b in SearchQuerySet().filter(indexed_model_name__in=["Bill"], content=q).order_by('-current_status_date')[0:9]]
    else:
        #bills = [{"href": bill.get_absolute_url(), "label": bill.title, "obj": bill, "secondary": bill.congress != CURRENT_CONGRESS }]
        return HttpResponseRedirect(bill.get_absolute_url())
    results.append(("Bills and Resolutions (Federal)", "/congress/bills/browse", "text", bills))

    results.append(("State Legislation", "/states/bills/browse", "text",
        [{"href": p.object.get_absolute_url(), "label": p.object.short_display_title, "obj": p.object, "secondary": False } for p in SearchQuerySet().using('states').filter(indexed_model_name__in=["StateBill"], content=q)[0:9]]))

    # in each group, make sure the secondary results are placed last, but otherwise preserve order
    for grp in results:
        for i, obj in enumerate(grp[3]):
           obj["index"] = i
        grp[3].sort(key = lambda o : (o.get("secondary", False), o["index"]))
    
    # sort categories first by whether all results are secondary results, then by number of matches (fewest first, if greater than zero)
    results.sort(key = lambda c : (len([d for d in c[3] if d.get("secondary", False) == False]) == False, len(c[3]) == 0, len(c[3])))
        
    return { "results": results }
    
@cache_page(60 * 15)
@render_to('website/campaigns/bulkdata2.html')
def campaign_bulk_data(request):
    return { }

@render_to('website/campaigns/bulkdata.html')
def campaign_bulk_data_old(request):
    prefixes = ("Mr.", "Ms.", "Mrs.", "Dr.")
    
    # Validate.
    if request.method == 'POST':
        from models import CampaignSupporter

        s = CampaignSupporter()
        
        if "sid" in request.POST:
            try:
                s = CampaignSupporter.objects.get(id=request.POST.get("sid"), email=request.POST.get("email", ""))
            except:
                pass
        
        s.campaign = "2012_03_buldata"
        for field in ('prefix', 'firstname', 'lastname', 'address', 'city', 'state', 'zipcode', 'email'):
            if request.POST.get(field, '').strip() == "":
                return { "stage": 1, "error": "All fields are required!", "prefixes": prefixes }
            setattr(s, field, request.POST.get(field, ""))
        s.message = request.POST.get('message', '')
        s.save()

        if "message" not in request.POST:
            return { "stage": 2, "sid": s.id }
        else:
            return { "stage": 3 }
    return { "stage": 1, "prefixes": prefixes }

def push_to_social_media_rss(request):
    import django.contrib.syndication.views
    from events.models import Feed
    from events.templatetags.events_utils import render_event
    import re
    
    feedlist = [Feed.from_name("misc:comingup"), Feed.from_name('misc:enactedbills')]
    
    class DjangoFeed(django.contrib.syndication.views.Feed):
        title = "GovTrack.us Is Tracking Congress"
        link = "/"
        description = "GovTrack tracks the activities of the United States Congress. We push this feed to our Twitter and Facebook accounts."
        
        def items(self):
            events = [render_event(item, feedlist) for item in Feed.get_events_for(feedlist, 25)]
            return [e for e in events if e != None]
            
        def item_title(self, item):
            return re.sub(r"^Legislation ", "", item["type"]) + ": " + item["title"]
        def item_description(self, item):
            return item["body_text"]
        def item_link(self, item):
            return "http://www.govtrack.us" + item["url"]# + "?utm_campaign=govtrack_push&utm_source=govtrack_push" 
        def item_guid(self, item):
            return "http://www.govtrack.us/events/guid/" + item["guid"] 
        def item_pubdate(self, item):
            return item["date"] if isinstance(item["date"], datetime) else datetime.combine(item["date"], time.min)
            
    return DjangoFeed()(request)

from website.api import api_overview


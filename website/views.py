# -*- coding: utf-8 -*-
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import redirect, get_object_or_404, render_to_response
from django.template import RequestContext
from django.core.urlresolvers import reverse
from django.core.cache import cache

from common.decorators import render_to
from common.pagination import paginate

from cache_utils.decorators import cached

from events.models import Feed

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
    return render_to_response('website/' + pagename + '.html', { "pagename": pagename }, RequestContext(request))

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
    
    results.append(("People", "/congress/members", "name",
        [{"href": p.object.get_absolute_url(), "label": p.object.name, "obj": p.object, "secondary": p.object.get_current_role() == None } for p in SearchQuerySet().filter(indexed_model_name__in=["Person"], content=q)[0:9]]))
        
    import us
    results.append(("States", "/congress/members", "most_recent_role_state",
        sorted([{"href": "/congress/members/%s" % s, "label": us.statenames[s] }
            for s in us.statenames
            if us.statenames[s].lower().startswith(q.lower())
            ], key=lambda p : p["label"])))
    
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
            [{"href": b.object.get_absolute_url(), "label": b.object.title, "obj": b.object, "secondary": b.object.congress != CURRENT_CONGRESS } for b in SearchQuerySet().filter(indexed_model_name__in=["Bill"], content=q)[0:9]]
    else:
        #bills = [{"href": bill.get_absolute_url(), "label": bill.title, "obj": bill, "secondary": bill.congress != CURRENT_CONGRESS }]
        return HttpResponseRedirect(bill.get_absolute_url())
    results.append(("Bills and Resolutions", "/congress/bills/browse", "text", bills))
    
    # sort first by whether all results are secondary results, then by number of matches (fewest first, if greater than zero)
    results.sort(key = lambda c : (len([d for d in c[3] if d.get("secondary", False) == False]) == False, len(c[3]) == 0, len(c[3])))
        
    return { "results": results }
    
@render_to('website/campaigns/bulkdata.html')
def campaign_bulk_data(request):
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



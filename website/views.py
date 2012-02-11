# -*- coding: utf-8 -*-
from django.http import Http404
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
        events_feed = Feed.get_events_for(None, 6)
        cache.set("frontpage_events_feed", events_feed, 60*15) # 15 minutes

    return {
        'events': events_feed,
        'tweets': twitter_feed,
        'blog': blog_feed,
        }
          
def staticpage(request, pagename):
    if pagename == "developers": pagename = "developers/index"
    return render_to_response('website/' + pagename + '.html', { }, RequestContext(request))

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

@render_to('website/congress_home.html')
def congress_home(request):
    return {}
    
@render_to('website/search.html')
def search(request):
    q = request.REQUEST.get("q", "")
    if q.strip() == "":
        return { "results": [] }
    
    results = []
    
    from person.models import Person
    results.append(("People", "/congress/members",
        sorted([{"href": p.get_absolute_url(), "label": p.name, "obj": p, "secondary": p.get_current_role() == None } for p in Person.objects.filter(lastname__contains=q)]
            , key=lambda p : (p["secondary"], p["obj"].sortname))))
        
    import us
    results.append(("States", "/congress/members",
        sorted([{"href": "/congress/members/%s" % s, "label": us.statenames[s] }
            for s in us.statenames
            if us.statenames[s].lower().startswith(q.lower())
            ], key=lambda p : p["label"])))
    
    from committee.models import Committee
    results.append(("Committees", "/congress/committees",
        sorted([{"href": c.get_absolute_url(), "label": c.fullname(), "obj": c }
        for c in Committee.objects.filter(name__contains=q, obsolete=False)]
        , key=lambda c : c["label"])))
       
    # TODO: Replace this with our own search if we want to go back into the archives...
    import urllib, json
    from settings import POPVOX_API_KEY, CURRENT_CONGRESS
    results.append(("Bills and Resolutions", "/congress/bills", [
            { "href": "/congress/bills/%s/%s%d" % (rec["congressnumber"], rec["billtype"], rec["billnumber"]), "label": rec["title"], "secondary": rec["congressnumber"] != CURRENT_CONGRESS }
        for rec in json.load(urllib.urlopen("https://www.popvox.com/api/v1/bills/search?" + urllib.urlencode({ "q": q, "api_key": POPVOX_API_KEY })))["items"]
        if rec["billtype"] in ("hr", "hres", "hjres", "hconres", "s", "sres", "sjres", "sconres")
        ][0:15]))
    
    # sort first by whether all results are secondary results, then by number of matches (fewest first, if greater than zero)
    results.sort(key = lambda c : (len([d for d in c[2] if d.get("secondary", False) == False]) == False, len(c[2]) == 0, len(c[2])))
        
    return { "results": results }

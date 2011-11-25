# -*- coding: utf-8 -*-
from django.http import Http404
from django.shortcuts import redirect, get_object_or_404, render_to_response
from django.template import RequestContext
from django.core.urlresolvers import reverse

from common.decorators import render_to
from common.pagination import paginate

from cache_utils.decorators import cached

from events.models import Feed

from datetime import datetime, timedelta

@render_to('website/index.html')
def index(request):
    import twitter
    twitter_api = twitter.Api()
    
    # TODO cache
    return {
        'events': Feed.get_events_for(None).filter(when__lte=datetime.now())[0:6],
        'tweets': twitter_api.GetUserTimeline("govtrack", since_id=0, count=3),
        'blog': get_blog_items()[0:2],
        }
		  
def staticpage(request, pagename):
    if pagename == "developers": pagename = "developers/index"
    return render_to_response('website/' + pagename + '.html', { }, RequestContext(request))

_blog_items = None
_blog_updated = None
def get_blog_items():
	global _blog_items
	global _blog_updated

	if _blog_items == None or datetime.now() - _blog_updated > timedelta(minutes=60):
		
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
		_blog_items = [{"link":entry.link, "title":decode_unicode_references(entry.title), "date":datetime(*entry.updated_parsed[0:6]), "content":decode_unicode_references(entry.content[0].value)} for entry in feed["entries"][0:4]]
		_blog_updated = datetime.now()
	return _blog_items

@render_to('website/congress_home.html')
def congress_home(request):
    return {}
    
@render_to('website/search.html')
def search(request):
    return {}

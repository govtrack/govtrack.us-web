# -*- coding: utf-8 -*-
from django.http import Http404
from django.shortcuts import redirect, get_object_or_404, render_to_response
from django.template import RequestContext
from django.core.urlresolvers import reverse

from common.decorators import render_to
from common.pagination import paginate

from cache_utils.decorators import cached

from events import feeds

from datetime import datetime

@render_to('website/index.html')
def index(request):
    import twitter
    api = twitter.Api()
    
    # TODO cache
    return {
        'events': feeds.Feed.get_events_for(None).filter(when__lte=datetime.now())[0:8],
        'tweets': api.GetUserTimeline("govtrack", since_id=0, count=5),
        }
		  
def staticpage(request, pagename):
    if pagename == "developers": pagename = "developers/index"
    return render_to_response('website/' + pagename + '.html', { }, RequestContext(request))

@render_to('website/congress_home.html')
def congress_home(request):
    return {}

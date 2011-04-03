# -*- coding: utf-8 -*-
from django.shortcuts import redirect, get_object_or_404
from django.core.urlresolvers import reverse
from django.http import HttpResponse

from common.decorators import render_to
from common.pagination import paginate

from datetime import datetime
import simplejson

import feeds
from models import *

@render_to('events/events_list.html')
def events_list(request):
    feedlist = request.GET.get('feeds', '').split(',')
    if feedlist == [""]:
        feedlist = []
    else:
        feedlist = [feeds.Feed.from_name(f) for f in feedlist]
        
    qs = feeds.Feed.get_events_for(feedlist if len(feedlist) > 0 else None).filter(when__lte=datetime.now()) # get all events
    page = paginate(qs, request, per_page=50)
    
    no_arg_feeds = [feeds.ActiveBillsFeed(), feeds.IntroducedBillsFeed(), feeds.ActiveBillsExceptIntroductionsFeed(), feeds.EnactedBillsFeed(), feeds.AllVotesFeed(), feeds.AllCommitteesFeed()]
    no_arg_feeds = [(feed, False) for feed in no_arg_feeds]
        
    return {
        'page': page,
        'no_arg_feeds': no_arg_feeds,
        'feeds': feedlist,
        'feeds_json': simplejson.dumps([f.getname() for f in feedlist]),
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
   

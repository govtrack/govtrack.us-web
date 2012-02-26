# -*- coding: utf-8 -*-
import os
from datetime import datetime, timedelta
from math import log, sqrt

from django.shortcuts import redirect, get_object_or_404
from django.core.urlresolvers import reverse

from common.decorators import render_to
from common.pagination import paginate

import json

from us import statelist, statenames, stateapportionment

from person.models import Person, PersonRole
from person import analysis
from person.types import RoleType
from person.video import get_youtube_videos, get_sunlightlabs_videos
from person.util import get_committee_assignments

from events.models import Feed

from smartsearch.manager import SearchManager
from search import person_search_manager

@render_to('person/person_details.html')
def person_details(request, pk):
    person = get_object_or_404(Person, pk=pk)
    
    # redirect to canonical URL
    if request.path != person.get_absolute_url():
        return redirect(person.get_absolute_url(), permanent=True)
       
    # current role
    role = person.get_current_role()
    if role:
        active_role = True
    else:
        active_role = False
        try:
            role = person.roles.order_by('-enddate')[0]
        except PersonRole.DoesNotExist:
            role = None

    # photo
    photo_path = 'data/photos/%d-100px.jpeg' % person.pk
    photo_credit = None
    if os.path.exists(photo_path):
        photo = '/' + photo_path
        with open(photo_path.replace("-100px.jpeg", "-credit.txt"), "r") as f:
            photo_credit = f.read().strip().split(" ", 1)
    else:
        photo = None

    analysis_data = analysis.load_data(person)

    videos = []

    if person.youtubeid:
        yt_videos = get_youtube_videos(person.youtubeid)
        videos.extend(yt_videos['videos'])

    #if person.bioguideid:
        #sunlight_videos = get_sunlightlabs_videos(person.bioguideid)
        ##sunlight_videos = get_sunlightlabs_videos('H001032')
        #videos.extend(sunlight_videos['videos'])

    recent_video = None
    if videos:
        videos.sort(key=lambda x: x['published'], reverse=True)
        if videos[0]['published'] > datetime.now() - timedelta(days=10):
            recent_video = videos[0]
            videos = videos[1:]

    # We are intrested only in four videos
    videos = videos[:4]

    return {'person': person,
            'role': role,
            'active_role': active_role,
            'photo': photo,
            'photo_credit': photo_credit,
            'analysis_data': analysis_data,
            'recent_bills': person.sponsored_bills.all().order_by('-introduced_date')[0:7],
            'recent_video': recent_video,
            'videos': videos,
            'committeeassignments': get_committee_assignments(person),
            'feed': Feed.PersonFeed(person.id),
            }


def searchmembers(request, initial_mode=None):
    return person_search_manager().view(request, "person/person_list.html",
        defaults = {
        	"roles__current": True if initial_mode=="current" else False,
        	"name": request.GET["name"] if "name" in request.GET else None,
        	},
        noun = ('person', 'people') )

def http_rest_json(url, args=None, method="GET"):
    import urllib, urllib2, json
    if method == "GET" and args != None:
        url += "?" + urllib.urlencode(args).encode("utf8")
    req = urllib2.Request(url)
    r = urllib2.urlopen(req)
    return json.load(r, "utf8")
    
@render_to('person/district_map.html')
def browsemembersbymap(request, state=None, district=None):
    center_lat, center_long, center_zoom = (38, -96, 4)
    
    sens = None
    reps = None
    if state != None:
        if stateapportionment[state] != "T":
            sens = Person.objects.filter(roles__current=True, roles__state=state, roles__role_type=RoleType.senator)
            sens = list(sens)
            for i in xrange(2-len(sens)): # make sure we list at least two slots
                sens.append(None)
    
        reps = []
        if stateapportionment[state] in ("T", 1):
            dists = [0]
            if district != None:
                raise Http404()
        else:
            dists = xrange(1, stateapportionment[state]+1)
            if district != None:
                if int(district) < 1 or int(district) > stateapportionment[state]:
                    raise Http404()
                dists = [int(district)]
        for i in dists:
            try:
                reps.append((i, Person.objects.get(roles__current=True, roles__state=state, roles__role_type=RoleType.representative, roles__district=i)))
            except Person.DoesNotExist:
                reps.append((i, None))
        
        try:
            info = cached(60*60*24)(http_rest_json)(
                "http://www.govtrack.us/perl/wms/list-regions.cgi",
                {
                "dataset": "http://www.rdfabout.com/rdf/usgov/us/states" if district == None else "http://www.rdfabout.com/rdf/usgov/congress/house/110",
                "uri": "http://www.rdfabout.com/rdf/usgov/geo/us/" + state.lower() + ("/cd/110/" + district if district != None else ""),
                "fields": "coord,area",
                "format": "json"
                  })["regions"][0]
            
            center_long, center_lat = info["long"], info["lat"]
            center_zoom = round(1.5 - log(sqrt(info["area"])/24902.0))
        except:
            pass
    
    return {
        "center_lat": center_lat,
        "center_long": center_long,
        "center_zoom": center_zoom,
        "state": state,
        "district": district,
        "statename": statenames[state] if state != None else None,
        "statelist": statelist,
        "senators": sens,
        "reps": reps,
    }

@render_to('person/district_map_embed.html')
def districtmapembed(request):
    return {
        "demo": "demo" in request.GET,
        "state": request.GET.get("state", ""),
        "district": request.GET.get("district", ""),
        "bounds": request.GET.get("bounds", None),
    }

@render_to('congress/political_spectrum.html')
def political_spectrum(request):
    rows = []
    fnames = [
        'data/us/112/stats/sponsorshipanalysis_h.txt',
        'data/us/112/stats/sponsorshipanalysis_s.txt',
    ]
    alldata = open(fnames[0]).read() + open(fnames[1]).read()
    for line in alldata.splitlines():
        chunks = [x.strip() for x in line.strip().split(',')]
        if chunks[0] == "ID":
            continue
        
        data = { }
        data['id'] = chunks[0]
        data['x'] = float(chunks[1])
        data['y'] = float(chunks[2])
        
        p = Person.objects.get(id=chunks[0])
        data['label'] = p.lastname
        if p.birthday: data['age'] = (datetime.now().date() - p.birthday).days / 365.25
        data['gender'] = p.gender
        
        r = p.get_last_role_at_congress(112)
        data['type'] = r.role_type
        data['party'] = r.party
        data['years_in_congress'] = (min(datetime.now().date(),r.enddate) - p.roles.filter(startdate__lte=r.startdate).order_by('startdate')[0].startdate).days / 365.25
        
        rows.append(data)
        
    years_in_congress_max = max([data['years_in_congress'] for data in rows])
    
    return {
        "data": json.dumps(rows),
        "years_in_congress_max": years_in_congress_max,
        }


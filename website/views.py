# -*- coding: utf-8 -*-
from lxml.etree import fromstring

from django.http import Http404
from django.shortcuts import redirect, get_object_or_404, render_to_response
from django.template import RequestContext
from django.core.urlresolvers import reverse

from common.decorators import render_to
from common.pagination import paginate

from cache_utils.decorators import cached

import json

@render_to('website/index.html')
def index(request):
    data = '<root><child><world>world!!</world></child></root>'
    world = fromstring(data).xpath('//world/text()')[0]
    return {'world': world,
            }
		  
def staticpage(request, pagename):
    if pagename == "developers": pagename = "developers/index"
    return render_to_response('website/' + pagename + '.html', { }, RequestContext(request))
   
def http_rest_json(url, args=None, method="GET"):
    import urllib, urllib2, json
    if method == "GET" and args != None:
        url += "?" + urllib.urlencode(args).encode("utf8")
    print url
    req = urllib2.Request(url)
    r = urllib2.urlopen(req)
    return json.load(r, "utf8")
    
@render_to('website/district_map.html')
def browsemembers(request, state, district):
    from us import statelist, statenames, stateapportionment
    from person.models import Person
    from person.types import RoleType
    from math import log, sqrt
    
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

		  
@render_to('congress/political_spectrum.html')
def political_spectrum(request):
    import person.models
    from datetime import datetime
    
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
        
        p = person.models.Person.objects.get(id=chunks[0])
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

@render_to('website/congress_home.html')
def congress_home(request):
    return {}

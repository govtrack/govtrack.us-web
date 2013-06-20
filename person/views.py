# -*- coding: utf-8 -*-
import os
from datetime import datetime, timedelta
from math import log, sqrt

from django.shortcuts import redirect, get_object_or_404
from django.core.urlresolvers import reverse
from django.db import connection
from django.db.models import Count
from django.http import Http404
from django.core.cache import cache

from common.decorators import render_to
from common.pagination import paginate

import json, cPickle, base64, re

from us import statelist, statenames, stateapportionment, state_abbr_from_name, stateabbrs, get_congress_dates

from person.models import Person, PersonRole
from person import analysis
from person.types import RoleType
from person.util import get_committee_assignments

from events.models import Feed

from smartsearch.manager import SearchManager
from search import person_search_manager

from registration.helpers import json_response
from twostream.decorators import anonymous_view, user_view_for

from settings import CURRENT_CONGRESS

@anonymous_view
@render_to('person/person_details.html')
def person_details(request, pk):
    def build_info():
        if re.match(r"\d", pk):
            person = get_object_or_404(Person, pk=pk)
        else:
            # support bioguide IDs for me
            person = get_object_or_404(Person, bioguideid=pk)
        
        # current role
        role = person.get_current_role()
        if role:
            active_role = True
        else:
            active_role = False
            try:
                role = person.roles.order_by('-enddate')[0]
            except IndexError:
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
        
        links = []
        if person.osid: links.append(("OpenSecrets.org", "http://www.opensecrets.org/politicians/summary.php?cid=" + person.osid))
        if person.pvsid: links.append(("VoteSmart.org", "http://votesmart.org/candidate/" + person.pvsid))
        if person.bioguideid: links.append(("Congress.gov", "http://bioguide.congress.gov/scripts/biodisplay.pl?index=" + person.bioguideid))
        if person.cspanid: links.append(("C-SPAN Video", "http://www.c-spanvideo.org/person/" + str(person.cspanid)))
    
        return {'person': person,
                'role': role,
                'active_role': active_role,
                'active_congressional_role': active_role and role.role_type in (RoleType.senator, RoleType.representative),
                'photo': photo,
                'photo_credit': photo_credit,
                'links': links,
                'analysis_data': analysis_data,
                'recent_bills': person.sponsored_bills.all().order_by('-introduced_date')[0:7],
                'committeeassignments': get_committee_assignments(person),
                'feed': Feed.PersonFeed(person.id),
                'cities': get_district_cities("%s-%02d" % (role.state.lower(), role.district)) if role and role.district else None,
                }

    ck = "person_details_%s" % pk
    ret = cache.get(ck)
    if not ret:
        ret = build_info()
        cache.set(ck, ret, 600)

    # redirect to canonical URL
    if request.path != ret["person"].get_absolute_url():
        return redirect(ret["person"].get_absolute_url(), permanent=True)
           
    return ret

@user_view_for(person_details)
def person_details_user_view(request, pk):
    person = get_object_or_404(Person, pk=pk)
    return render_subscribe_inline(request, Feed.PersonFeed(person.id))

def render_subscribe_inline(request, feed):
    # render the event subscribe button, but fake the return path
    # by overwriting our current URL
    from django.template import Template, Context, RequestContext, loader
    request.path = request.GET["path"]
    request.META["QUERY_STRING"] = ""
    events_button = loader.get_template("events/subscribe_inline.html")\
        .render(RequestContext(request, {
				'feed': feed,
				}))
    return { 'events_subscribe_button': events_button }
                
@anonymous_view
def searchmembers(request, initial_mode=None):
    return person_search_manager().view(request, "person/person_list.html",
        defaults = {
            "is_currently_moc": True if initial_mode=="current" else False,
            "text": request.GET["name"] if "name" in request.GET else None,
            },
        noun = ('person', 'people') )

def http_rest_json(url, args=None, method="GET"):
    import urllib, urllib2, json
    if method == "GET" and args != None:
        url += "?" + urllib.urlencode(args).encode("utf8")
    req = urllib2.Request(url)
    r = urllib2.urlopen(req)
    return json.load(r, "utf8")
    
@anonymous_view
@render_to('person/district_map.html')
def browsemembersbymap(request, state=None, district=None):
    center_lat, center_long, center_zoom = (38, -96, 4)
    
    sens = None
    reps = None
    if state != None:
        if state.lower() in state_abbr_from_name:
            state = state_abbr_from_name[state.lower()]
        elif state.upper() not in statenames:
            raise Http404()
        else:
            state = state.upper()
       
        # Load senators for all states that are not territories.
        if stateapportionment[state] != "T":
            sens = Person.objects.filter(roles__current=True, roles__state=state, roles__role_type=RoleType.senator)
            sens = list(sens)
            for i in xrange(2-len(sens)): # make sure we list at least two slots
                sens.append(None)
    
        # Load representatives for at-large districts.
        reps = []
        if stateapportionment[state] in ("T", 1):
            dists = [0]
            if district != None:
                raise Http404()
                
        # Load representatives for non-at-large districts.
        else:
            dists = xrange(1, stateapportionment[state]+1)
            if district != None:
                if int(district) < 1 or int(district) > stateapportionment[state]:
                    raise Http404()
                dists = [int(district)]
        
        for i in dists:
            cities = get_district_cities("%s-%02d" % (state.lower(), i)) if i > 0 else None
            try:
                reps.append((i, Person.objects.get(roles__current=True, roles__state=state, roles__role_type=RoleType.representative, roles__district=i), cities))
            except Person.DoesNotExist:
                reps.append((i, None, cities))

        zoom_info_cache_key = "map_zoom_%s-%s" % (state, "" if not district else district)

        if state == "MP":
            center_long, center_lat, center_zoom = (145.7, 15.1, 11.0)
        elif state == "AS":
            center_long, center_lat, center_zoom = (-170.255127, -14.514462, 8.0)
        elif state == "HI":
            center_long, center_lat, center_zoom = (-155.5, 20, 7.0)
        elif state == "AK":
            # Alaska has a longitude wrap-around problem so it's easier to just specify
            # the coordinates manually than to figure out generically how to do the math
            # of taking the average of the bounding box coordinates.
            center_long, center_lat, center_zoom = (-150, 63, 4.0)
        elif cache.get(zoom_info_cache_key):
            center_lat, center_long, center_zoom = cache.get(zoom_info_cache_key)
        else:
            def get_coords(state, distr):
                import urllib, json
                if not distr:
                    url = "http://gis.govtrack.us/boundaries/2012-states/%s/?format=json" % state.lower()
                else:
                    url = "http://gis.govtrack.us/boundaries/cd-2012/%s-%02d/?format=json" % (state.lower(), int(distr))
                resp = json.load(urllib.urlopen(url))
                sw_lng, sw_lat, ne_lng, ne_lat = resp["extent"]
                area = (ne_lng-sw_lng)*(ne_lat-sw_lat)
                center_long, center_lat = (sw_lng+ne_lng)/2.0, (sw_lat+ne_lat)/2.0
                center_zoom = round(1.0 - log(sqrt(area)/1000.0))
                return center_lat, center_long, center_zoom
                
            center_lat, center_long, center_zoom = get_coords(state, None)
            
            # Zoom in to district if it is too small to be seen on a whole-state map.
            if district:
                distr_center_lat, district_center_long, district_center_zoom = get_coords(state, district)
                if district_center_zoom > center_zoom + 1:
                    center_lat, center_long, center_zoom = distr_center_lat, district_center_long, district_center_zoom
                    
            cache.set(zoom_info_cache_key, (center_lat, center_long, center_zoom) )
    
    return {
        "center_lat": center_lat,
        "center_long": center_long,
        "center_zoom": center_zoom,
        "state": state,
        "district": int(district) if district else None,
        "district_zero": ("%02d" % int(district)) if district else None,
        "stateapp": stateapportionment[state] if state != None else None,
        "statename": statenames[state] if state != None else None,
        "statelist": statelist,
        "senators": sens,
        "reps": reps,
        "cities": get_district_cities("%s-%02d" % (state.lower(), int(district))) if state and district else None,
    }
    
def get_district_cities(district_id):
    district_info = cache.get("district_cities_%s" % district_id)
    if district_info:
        if district_info == "NONE": district_info = None
        return district_info
    
    # When debugging locally, this file may not exist.
    if os.path.exists("data/misc/cd-intersection-data.json"):
        district_info = json.load(open("data/misc/cd-intersection-data.json")).get(district_id)
    else:
        district_info = None
    if district_info:
        locations_1 = [c["name"] for c in sorted(district_info, key=lambda c:-c["pct_of_district"]) if c["pct_of_locality"] > .98][0:8]
        locations_2 = [c["name"] for c in sorted(district_info, key=lambda c:-c["pct_of_locality"]) if c["pct_of_locality"] <= .98][0:8]
        district_info = ", ".join(locations_1)
        if len(locations_2) > 2:
            if len(locations_1) > 0:
                district_info += " and parts of "
                locations_2 = locations_2[0:5]
            else:
                district_info += "Parts of "
            district_info += ", ".join(locations_2)
    
    cache.set("district_cities_%s" % district_id, district_info if district_info != None else "NONE")
    
    return district_info
    
@anonymous_view
@render_to('person/overview.html')
def membersoverview(request):
    def get_current_members(role_type, delegates, by_party):
        qs = PersonRole.objects.filter(
            role_type=role_type,
            current=True,
            state__in=set(s for s, t in stateapportionment.items() if (t != "T") ^ delegates)
            )
        if by_party:
            return qs.values('party').annotate(count=Count('party')).order_by('-count')
        else:
            return qs.count()
    
    congress_current = (CURRENT_CONGRESS, get_congress_dates(CURRENT_CONGRESS)[0])
    congress_previous = (CURRENT_CONGRESS-1, get_congress_dates(CURRENT_CONGRESS-1)[1])
            
    return {
        "statelist": statelist,
        "senate_by_party": get_current_members(RoleType.senator, False, True),
        "senate_vacancies": 100-get_current_members(RoleType.senator, False, False),
        "house_by_party": get_current_members(RoleType.representative, False, True),
        "house_vacancies": 435-get_current_members(RoleType.representative, False, False),
        "house_delegate_vacancies": 6-get_current_members(RoleType.representative, True, False),
        "congress_current": congress_current,
        "congress_previous": congress_previous,
    }

@anonymous_view
@render_to('person/district_map_embed.html')
def districtmapembed(request):
    return {
        "demo": "demo" in request.GET,
        "state": request.GET.get("state", ""),
        "district": request.GET.get("district", ""),
        "bounds": request.GET.get("bounds", None),
    }
    
@anonymous_view
@json_response
def district_lookup(request):
    lng, lat = float(request.GET.get("lng", "0")), float(request.GET.get("lat", "0"))
    return do_district_lookup(lng, lat)

def do_district_lookup(lng, lat):
    import urllib, json
    url = "http://gis.govtrack.us/boundaries/cd-2012/?contains=%f,%f&format=json" % (lat, lng)
    try:
        resp = json.load(urllib.urlopen(url))
    except Exception as e:
        return { "error": "error loading district data (%s)" % str(e) }
    
    if len(resp["objects"]) == 0:
        return { "error": "point is not within a district" }

    if len(resp["objects"]) > 1:
        return { "error": "point is within multiple districts!" }
        
    d = resp["objects"][0]["external_id"].split("-")
    return { "state": d[0].upper(), "district": int(d[1]) }

import django.contrib.sitemaps
class sitemap_current(django.contrib.sitemaps.Sitemap):
    changefreq = "weekly"
    priority = 1.0
    def items(self):
        return Person.objects.filter(roles__current=True).distinct()
class sitemap_archive(django.contrib.sitemaps.Sitemap):
    changefreq = "yearly"
    priority = 0.25
    def items(self):
        return Person.objects.filter(roles__current=False).distinct()
class sitemap_districts(django.contrib.sitemaps.Sitemap):
    changefreq = "monthly"
    priority = 0.5
    def items(self):
        ret = []
        for state in stateabbrs:
            if state not in stateapportionment: continue
            ret.append( (state, 0) )
            if stateapportionment[state] not in (1, "T"):
                for district in xrange(1, stateapportionment[state]+1):
                    ret.append( (state, district) )
        return ret
    def location(self, item):
        return "/congress/members/" + item[0] + ("/"+str(item[1]) if item[1] else "")
        

# -*- coding: utf-8 -*-
import os
from datetime import datetime, timedelta
from math import log, sqrt

from django.shortcuts import redirect, get_object_or_404
from django.core.urlresolvers import reverse
from django.db import connection
from django.db.models import Count
from django.http import Http404, HttpResponse
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
        photo_url, photo_credit = person.get_photo()
    
        # analysis
        analysis_data = analysis.load_data(person)
        has_session_stats = False
        if role:
            #try:
                has_session_stats = role.get_most_recent_session_stats()
            #except:
            #s    pass
        
        links = []
        if person.osid: links.append(("OpenSecrets", "http://www.opensecrets.org/politicians/summary.php?cid=" + person.osid))
        if person.pvsid: links.append(("VoteSmart", "http://votesmart.org/candidate/" + person.pvsid))
        if person.bioguideid: links.append(("Bioguide", "http://bioguide.congress.gov/scripts/biodisplay.pl?index=" + person.bioguideid))
        if person.cspanid: links.append(("C-SPAN Video", "http://www.c-spanvideo.org/person/" + str(person.cspanid)))
    
        return {'person': person,
                'role': role,
                'active_role': active_role,
                'active_congressional_role': active_role and role.role_type in (RoleType.senator, RoleType.representative),
                'photo': photo_url,
                'photo_credit': photo_credit,
                'links': links,
                'analysis_data': analysis_data,
                'recent_bills': person.sponsored_bills.all().order_by('-introduced_date')[0:7],
                'committeeassignments': get_committee_assignments(person),
                'feed': Feed.PersonFeed(person.id),
                'cities': get_district_cities("%s-%02d" % (role.state.lower(), role.district)) if role and role.district else None,
                'has_session_stats': has_session_stats,
                }

    #ck = "person_details_%s" % pk
    #ret = cache.get(ck)
    #if not ret:
    #    ret = build_info()
    #    cache.set(ck, ret, 600)
    ret = build_info()

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
            sens = Person.objects.filter(roles__current=True, roles__state=state, roles__role_type=RoleType.senator)\
                .order_by('roles__senator_rank')
            sens = list(sens)

            # make sure we list at least two slots, filling with Vacant if needed
            for i in xrange(2-len(sens)): sens.append(None)
    
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

        center_lat, center_long, center_zoom = get_district_bounds(state, district)
            
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
    
def get_district_bounds(state, district):
    zoom_info_cache_key = "map_zoom_%s-%s" % (state, "" if not district else district)

    if state == "MP":
        return (145.7, 15.1, 11.0)
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

    return (center_lat, center_long, center_zoom)

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
    bounds2 = None
    try:
        bounds2 = get_district_bounds(request.GET.get("state", ""), request.GET.get("district", ""))
    except:
        pass

    return {
        "demo": "demo" in request.GET,
        "hide_footer": "demo" in request.GET or "footer" in request.GET,
        "state": request.GET.get("state", ""),
        "district": request.GET.get("district", ""),
        "bounds": request.GET.get("bounds", None),
        "bounds2": bounds2,
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
        
@anonymous_view
@render_to('person/person_session_stats.html')
def person_session_stats(request, pk, session):
    # get the person and the statistics
    person = get_object_or_404(Person, pk=pk)
    try:
        stats = person.get_session_stats(session)
    except ValueError:
        # no stats
        raise Http404()

    # get the role as stored in the file
    role = PersonRole.objects.get(id=stats["role_id"])

    stat_titles = {
        "missed-votes":  { "title": "Missed Votes", "icon": "voting-records" },
        "bills-introduced":  { "title": "Bills Introduced", "icon": "bills-resolutions" },
        "bills-enacted":  { "title": "Laws Enacted", "icon": "bills-resolutions" },
        "bills-reported":  { "title": "Bills Out of Committee", "icon": "committees" },
        "bills-with-committee-leaders":  { "title": "Powerful Cosponsors", "icon": "committees" },
        "bills-with-cosponsors-both-parties":  { "title": "Writing Bipartisan Bills", "icon": "handshake" },
        "bills-with-companion":  { "title": "Working with the {{other_chamber}}", "icon": "handshake" },
        "cosponsors":  { "title": "Cosponsors", "icon": "congress-members" },
        "cosponsored":  { "title": "Bills Cosponsored", "icon": "bills-resolutions" },
        "cosponsored-other-party":  { "title": "Joining Bipartisan Bills", "icon": "handshake" },
        "ideology": { "title": "Ideology Score", "icon": "congress-members", "superlatives": ("most conservative", "most liberal") },
        "leadership":  { "title": "Leadership Score", "icon": "congress-members" },
        "committee-positions":  { "title": "Committee Positions", "icon": "committees" },
        "transparency-bills":  { "title": "Government Transparency", "icon": "open-government" },
    }

    # Remove ideology if the person has a low leadership score because it indicates bad data.
    # Remove it and leadership if the introduced fewer than ten bills.
    if stats["stats"]["bills-introduced"]["value"] < 10 or stats["stats"]["leadership"]["value"] < .25: del stats["stats"]["ideology"]
    if stats["stats"]["bills-introduced"]["value"] < 10: del stats["stats"]["leadership"]
    for s in list(stats["stats"].keys()):
        if stats["stats"][s]["value"] is None:
            del stats["stats"][s]

    # Delete some dumb other contexts.
    delete = [
        ("committee-positions", "senate-committee-leaders"),
        ("committee-positions", "house-committee-leaders"),
        ("missed-votes", "party-house-democrat"),
        ("missed-votes", "party-house-republican"),
        ("missed-votes", "party-house-independent"),
        ("missed-votes", "party-senate-democrat"),
        ("missed-votes", "party-senate-republican"),
        ("missed-votes", "party-senate-independent"),
        ]
    for statname, stat in stats["stats"].items():
        if "context" not in stat: continue
        for s, c in delete:
            if statname == s and c in stat["context"]:
                del stat["context"][c]

    # put nice names in the context cohorts
    def get_cohort_name(key):
        if key == "house": return "All Representatives"
        if key == "senate": return "All Senators"
        if key == "party-house-democrat": return "House Democrats"
        if key == "party-house-republican": return "House Republicans"
        if key == "party-house-independent": return "House Independents"
        if key == "party-senate-democrat": return "Senate Democrats"
        if key == "party-senate-republican": return "Senate Republicans"
        if key == "party-senate-independent": return "Senate Independents"
        if key.startswith("house-state-delegation-"): return statenames[key[23:25].upper()] + " Delegation"
        if key == "house-leadership": return "House Party Leaders"
        if key == "senate-leadership": return "Senate Party Leaders"
        if key == "house-freshmen": return "House Freshmen"
        if key == "senate-freshmen": return "Senate Freshmen"
        if key == "house-sophomores": return "House Sophomores"
        if key == "senate-sophomores": return "Senate Sophomores"
        if key == "house-tenyears": return "Serving 10+ Years"
        if key == "senate-tenyears": return "Senators Serving 10+ Years"
        if key == "house-committee-leaders": return "House Cmte. Chairs/RkMembs"
        if key == "senate-committee-leaders": return "Senate Cmte. Chairs/RkMembs"
        if key == "house-competitive-seat": return "Competitive House Seats"
        if key == "house-safe-seat": return "Safe House Seats"
        raise ValueError(key)
    for statname, stat in stats["stats"].items():
        stat["key"] = statname
        stat.update(stat_titles.get(statname, { "title": statname, "icon": "" }))
        stat["title"] = stat["title"].replace("{{other_chamber}}", stat.get("other_chamber",""))

        stat["show_values"] = statname not in ("leadership", "ideology")
        if "superlatives" not in stat: stat["superlatives"] = ("highest", "lowest")

        for cohort, context in stat.get("context", {}).items():
            context["key"] = cohort
            context["name"] = get_cohort_name(cohort)

            # If the person's rank is less than the number of ties, don't use this context
            # for the headline.
            if min(context["rank_ascending"], context["rank_descending"]) < context["rank_ties"]:
                context["use_in_headline"] = False

            # These are never interesting.
            if cohort == "house-safe-seat":
                context["use_in_headline"] = False

            # The percentile we computed off-line is the normal percentile, but it's not good for
            # "Top 20%"-style measures. Re-do it.
            context["percentile2"] = (min(context["rank_ascending"], context["rank_descending"]) + context["rank_ties"])/float(context["N"])

    stats["stats"] = list(stats["stats"].values())

    # Within each statistic, put the context cohorts into the most interesting
    # order for display, which is cohorts from smallest size to largest size.
    #
    # Also choose the context cohort that is best for the statistic's headline,
    # which is the cohort with the most extreme percentile, with ties favoring
    # the larger group.
    def cohort_comparer_for_display(cohort):
        return cohort["N"]
    def cohort_comparer_for_headline(cohort):
        return (min(cohort["percentile"], 100-cohort["percentile"]), -cohort["N"])
    for stat in stats["stats"]:
        if len(stat.get("context", {})) == 0: continue
        stat["context_for_display"] = sorted(stat["context"].values(), key = cohort_comparer_for_display)

        contexts_for_headline = [c for c in stat["context"].values() if c.get("use_in_headline", True)]
        if len(contexts_for_headline) > 0:
            stat["context_for_headline"] = sorted(contexts_for_headline, key = cohort_comparer_for_headline)[0]

    # put the statistics in the most interesting order, which is statistics
    # for which the member has the most extreme values to display.
    def stat_comparer(stat):
        if len(stat.get("context_for_headline", [])) == 0: return (999999, 0) # no contextual info, put last
        c = stat["context_for_headline"]
        return (min(c["rank_ascending"], c["rank_descending"]) + c["rank_ties"]/2.0, -c["N"])
    stats["stats"].sort(key = stat_comparer)

    # group into an order for navigation
    nav_groups = []
    for stat in stats["stats"]:
        for group in nav_groups:
            if group["icon"] == stat["icon"]:
                group["stats"].append(stat)
                break
        else:
            nav_groups.append({ "icon": stat["icon"], "stats": [stat]  })

    import dateutil
    from person.types import Gender, RoleType

    return {
        "publishdate": dateutil.parser.parse(stats["meta"]["as-of"]),
        "person": person,
        "photo": person.get_photo()[0],
        "himher": Gender.by_value(person.gender).pronoun_object,
        "role": role,
        "class": RoleType.by_value(role.role_type).label.lower() + "s",
        "session": session,
        "meta": stats["meta"],
        "stats": stats["stats"],
        "nav_groups": nav_groups,
    }

@anonymous_view
def person_session_stats_export(request, session, statistic, cohort):
    try:
        stats = Person.load_session_stats(session)
    except ValueError:
        # no stats
        raise Http404()

    # collect data
    rows = []
    for person_id, person_stats in stats["people"].items():
        if cohort not in [c["key"] for c in person_stats["cohorts"]]: continue
        if statistic not in person_stats["stats"]: continue
        rows.append([
            person_stats["stats"][statistic]["context"][cohort]["rank_ascending"],
            person_stats["stats"][statistic]["context"][cohort]["rank_descending"],
            person_stats["stats"][statistic]["context"][cohort]["percentile"],
            person_stats["stats"][statistic]["value"],
            int(person_id),
            int(person_stats["role_id"]),
            "",
            "",
            ])
    if len(rows) == 0:
        raise Http404()

    # assign sortname to the 2nd column so we can use it in sorting
    people = Person.objects.in_bulk([r[4] for r in rows])
    roles = PersonRole.objects.in_bulk([r[5] for r in rows])
    for r in rows:
        if r[4] not in people: continue # database mismatch, happens during testing
        r[5], r[6] = roles[r[5]].state, roles[r[5]].district if isinstance(roles[r[5]].district, int) else ""
        r[7] = people[r[4]].lastname.encode("utf-8")

    # sort
    rows.sort(key = lambda r : (r[0], r[5]))

    # turn into strings
    for r in rows:
        r[0] = unicode(r[0]).encode('utf-8')
        r[2] = unicode(r[2]).encode("utf-8")

    # format CSV
    import csv, StringIO
    outfile = StringIO.StringIO()
    writer = csv.writer(outfile)
    writer.writerow(["rank_from_low", "rank_from_high", "percentile", statistic, "id", "state", "district", "name"])
    for row in rows: writer.writerow(row)
    output = outfile.getvalue()

    # construct response
    r = HttpResponse(output, content_type='text/csv')
    r['Content-Disposition'] = 'attachment; filename=' + "govtrack-stats-%s-%s-%s.csv" % (session, statistic, cohort)
    return r

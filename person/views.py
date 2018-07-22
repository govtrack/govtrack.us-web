# -*- coding: utf-8 -*-
import os, os.path
from datetime import datetime, timedelta
from math import log, sqrt

from django.shortcuts import redirect, get_object_or_404
from django.core.urlresolvers import reverse
from django.db import connection
from django.db.models import Count
from django.http import Http404, HttpResponse
from django.core.cache import cache
from django.conf import settings

from common.decorators import render_to

import json, pickle, base64, re

from us import statelist, statenames, stateapportionment, state_abbr_from_name, stateabbrs, get_congress_dates

from person.models import Person, PersonRole
from person import analysis
from person.types import RoleType
from person.util import get_committee_assignments

from events.models import Feed

from smartsearch.manager import SearchManager
from .search import person_search_manager

from registration.helpers import json_response
from twostream.decorators import anonymous_view, user_view_for

from settings import CURRENT_CONGRESS

pronunciation_guide = None
pronunciation_guide_key = {
"a": "cat", "b": "bat",
"ah": "calm", "ch": "chin",
"air": "hair", "d": "day",
"ar": "bar", "f": "fat",
"aw": "law", "g": "get",
"ay": "say", "h": "hat",
"e": "bed", "j": "jam",
"ee": "meet", "k": "king",
"eer": "beer", "l": "leg",
"er": "her", "m": "man",
"ew": "few", "n": "not",
"i": "pin", "ng": "sing",
"ī": "eye", "nk": "thank",
"o": "top", "p": "pen",
"oh": "most", "r": "rag",
"oo": "soon", "s": "sit",
"oor": "poor", "t": "top",
"or": "corn", "th": "thin",
"ow": "cow", "t͡h": "this",
"oy": "boy", "v": "van",
"u": "cup", "w": "will",
"uh": "cup", "y": "yes",
"uu": "book", "z": "zebra",
"y": "cry", "zh": "vision",
"yoo": "unit",  "yr": "fire",
" ": None, "-": None,
}

@anonymous_view
@render_to('person/person_details.html')
def person_details(request, pk):
    def build_info():
        global pronunciation_guide

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
        try:
            # Get session stats for the previous year.
            has_session_stats = person.get_session_stats(str(datetime.now().year-1))
        except:
            # Not everyone has current stats, obviously. They may have stats
            # corresponding to their most recent role. Since stats are a
            # session behind, even-year stats might not correspond to
            # a legislator's most recent role, which is why I hard-coded
            # the current session stats above.
            has_session_stats = False
            if role:
                try:
                    has_session_stats = role.get_most_recent_session_stats()
                except:
                    pass
        
        links = []
        if role.current:
            if role.website: links.append(("%s's Official Website" % person.lastname, role.website, "fa fa-external-link"))
            if person.twitterid: links.append(("@" + person.twitterid, "http://twitter.com/" + person.twitterid, "fa fa-twitter"))
        if person.osid: links.append(("OpenSecrets", "http://www.opensecrets.org/politicians/summary.php?cid=" + person.osid, "fa fa-money"))
        if person.pvsid: links.append(("VoteSmart", "http://votesmart.org/candidate/" + person.pvsid, "fa fa-th-list"))
        if person.bioguideid: links.append(("Bioguide", "http://bioguide.congress.gov/scripts/biodisplay.pl?index=" + person.bioguideid, "fa fa-user"))
        if person.cspanid: links.append(("C-SPAN", "http://www.c-spanvideo.org/person/" + str(person.cspanid), "fa fa-youtube-play"))

        # Get a break down of the top terms this person's sponsored bills fall into,
        # looking only at the most recent five years of bills.
        from bill.models import BillTerm
        from datetime import datetime, timedelta
        most_recent_bill = person.sponsored_bills.order_by("-introduced_date").first()
        bills_by_subject_counts = list(person.sponsored_bills.filter(
            terms__id__in=BillTerm.get_top_term_ids(),
            introduced_date__gt=(most_recent_bill.introduced_date if most_recent_bill else datetime.now())-timedelta(days=5*365.25))\
            .values("terms")\
            .annotate(count=Count('id')).order_by('-count')\
            .filter(count__gt=1)\
            [0:8])
        terms = BillTerm.objects.in_bulk(item["terms"] for item in bills_by_subject_counts)
        total_count = sum(item["count"] for item in bills_by_subject_counts)
        while len(bills_by_subject_counts) > 2 and bills_by_subject_counts[-1]["count"] < bills_by_subject_counts[0]["count"]/8: bills_by_subject_counts.pop(-1)
        for item in bills_by_subject_counts:
            item["term"] = terms[item["terms"]]
            item["pct"] = int(round(float(item["count"]) / total_count * 100))
            del item["terms"]

        # Missed vote explanations from ProPublica
        try:
            vote_explanations = http_rest_json("https://projects.propublica.org/explanations/api/members/%s.json" % person.bioguideid)
        except: 
            # squash all errors
            vote_explanations = { }

        # Misconduct - load and filter this person's entries, keeping original order.
        # Choose 'Alleged misconduct', 'Misconduct', 'Misconduct/alleged misconduct' as appropriate.
        from website.views import load_misconduct_data
        misconduct = [m for m in load_misconduct_data() if m["person"] == person ]
        misconduct_any_alleged = (len([ m for m in misconduct if m["alleged"]  ]) > 0)
        misconduct_any_not_alleged = (len([ m for m in misconduct if not m["alleged"]  ]) > 0)

        # Load pronunciation from guide. Turn into a mapping from GovTrack IDs to data.
        if pronunciation_guide is None:
            import rtyaml
            if not os.path.exists("data/us/pronunciation.yaml"):
                # debugging
                pronunciation_guide = { }
            else:
                pronunciation_guide = { p["id"]["govtrack"]: p for p in rtyaml.load(open("data/us/pronunciation.yaml")) }

        # Get this person's entry.
        pronunciation = pronunciation_guide.get(person.id)
        # TODO: Validate that the 'name' in the guide matches the name we're actually displaying.
        if pronunciation:
          # Show a letter-pronunciation key including only the letters in the pronunciation respelling,
          # and excluding punctuation glyphs (which are used for syllabification and word boundaries).
          pronunciation["key"] = set()
          for namepart in pronunciation["respell"].split(" // "):
            # Parse out the letters actually used in the guide. Sweep from left to right chopping
            # off valid respelling letter combinations, chopping off the longest one where possible.
            i = 0
            while i < len(namepart):
              for s in sorted(pronunciation_guide_key, key = lambda s : -len(s)):
                if namepart[i:i+len(s)] in (s, s.upper()):
                  if pronunciation_guide_key[s]:
                    pronunciation["key"].add(s)
                  i += len(s)
                  break
              else:
                # respelling did not match any valid symbol
                break

          # Sort the letters. Because of the barred i, a standard lexicographic sort fails. Use NFKD to sort barred i after regular i.
          import unicodedata
          pronunciation["key"] = sorted(pronunciation["key"], key = lambda letter : unicodedata.normalize('NFKD', letter))

          # Turn letters into letter-guide pairs.
          pronunciation["key"] = [(letter, pronunciation_guide_key[letter]) for letter in pronunciation["key"]]

        enacted_bills_src_qs = person.sponsored_bills.exclude(original_intent_replaced=True).order_by('-current_status_date')

        return {'person': person,
                'role': role,
                'active_role': active_role,
                'active_congressional_role': active_role and role.role_type in (RoleType.senator, RoleType.representative),
                'pronunciation': pronunciation,
                'photo': photo_url,
                'photo_credit': photo_credit,
                'links': links,
                'analysis_data': analysis_data,
                'enacted_bills': [b for b in enacted_bills_src_qs if b.was_enacted_ex(cache_related_bills_qs=enacted_bills_src_qs)],
                'recent_bills': person.sponsored_bills.all().order_by('-introduced_date')[0:7],
                'committeeassignments': get_committee_assignments(person),
                'feed': person.get_feed(),
                'has_session_stats': has_session_stats,
                'bill_subject_areas': bills_by_subject_counts,
                'vote_explanations': vote_explanations,
                'key_votes': load_key_votes(person),
                'misconduct': misconduct,
                'misconduct_any_alleged': misconduct_any_alleged,
                'misconduct_any_not_alleged': misconduct_any_not_alleged,
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

def load_key_votes(person):
    # Get this person's key votes.

    from vote.models import Vote, Voter

    # First get all of the major votes that this person has participated in.
    all_votes = person.votes.filter(vote__category__in=Vote.MAJOR_CATEGORIES)
    congresses = sorted(set(all_votes.values_list("vote__congress", flat=True).distinct()), reverse=True)
    all_votes = all_votes.values_list("vote__id", flat=True)

    # We'll pick top votes where the person was an outlier (so the vote was informative
    # for this Member) and top where the person wasn't an outlier but had a lot of
    # outliers (so the vote was interesting).
    #
    # But we'll disperse the votes across the time period the Member served in:
    # 4 in the most recent two Congress, 4 after that.
    ret = []
    for congresses_set in [congresses[0:2], congresses[2:]]:
        # Scan the cached votes for the votes with the most number of outliers
        # and the votes that this person was an outlier in.
        import csv
        top_votes = { }
        outlier_votes = set()
        for congress in congresses_set:
            fn = "data/us/%d/stats/notable_votes.csv" % congress
            if not os.path.exists(fn): continue
            for vote in csv.DictReader(open(fn)):
                if int(vote["vote_id"]) not in all_votes: continue
                outliers = set(int(v) for v in vote["outliers"].split(" ") if v != "")
                top_votes[int(vote["vote_id"])] = len(outliers)
                if person.id in outliers: outlier_votes.add(int(vote["vote_id"]))

        # Sort the votes by the number of outliers.
        top_votes = sorted(top_votes.items(), key=lambda kv : -kv[1])
        top_votes = [kv[0] for kv in top_votes]

        ret += [v for v in top_votes if v in outlier_votes][0:3] \
             + [v for v in top_votes if v not in outlier_votes][0:2]

    # Convert to Vote objects, make unique, and order by vote date.
    ret = Vote.objects.filter(id__in=ret).order_by('-created')
    ret = sorted(ret, key = lambda v : v.created, reverse=True)

    # Replace with a tuple of the vote and the Voter object for this person.
    voters = { v.vote_id: v for v in Voter.objects.filter(vote__in=ret, person=person).select_related("option") }
    ret = [
        (vote, voters[vote.id])
        for vote in ret
    ]

    return ret

@user_view_for(person_details)
def person_details_user_view(request, pk):
    person = get_object_or_404(Person, pk=pk)
    return render_subscribe_inline(request, person.get_feed())

def render_subscribe_inline(request, feed):
    # render the event subscribe button, but fake the return path
    # by overwriting our current URL
    from django.template import Template, loader
    request.path = request.GET["path"]
    request.META["QUERY_STRING"] = ""
    events_button = loader.get_template("events/subscribe_inline.html")\
        .render({
				'feed': feed,
                'request': request,
				})
    return { 'events_subscribe_button': events_button }
                
@anonymous_view
def searchmembers(request, mode=None):
    return person_search_manager(mode).view(request, "person/person_list.html",
        defaults = {
            "text": request.GET["name"] if "name" in request.GET else None,
            },
        noun = ('person', 'people'),
        context = {
            "mode": mode, # "current" or "all"
        } )

def http_rest_json(url, args=None, method="GET"):
    import urllib.request, urllib.parse, urllib.error, urllib.request, urllib.error, urllib.parse, json
    if method == "GET" and args != None:
        url += "?" + urllib.parse.urlencode(args).encode("utf8")
    req = urllib.request.Request(url)
    r = urllib.request.urlopen(req, timeout=10)
    return json.load(r, "utf8")
    
@anonymous_view
@render_to('person/district_map.html')
def browse_map(request):
    return {
        "center_lat": 38, # # center the map on the continental US
        "center_long": -96,
        "center_zoom": 4,
        "statelist": statelist,
        "MAPBOX_ACCESS_TOKEN": settings.MAPBOX_ACCESS_TOKEN,
    	"MAPBOX_MAP_STYLE": settings.MAPBOX_MAP_STYLE,
    	"MAPBOX_MAP_ID": settings.MAPBOX_MAP_ID,
    }
    
def normalize_state_arg(state):
    if state.lower() in state_abbr_from_name:
        # Wikipedia links use state names!
        return state_abbr_from_name[state.lower()]
    elif state.upper() not in statenames:
        raise Http404()
    else:
        return state.upper()

def get_senators(state):
    # Load senators for all states that are not territories.
    if stateapportionment[state] == "T":
        return []

    # Order by rank.
    sens = Person.objects.filter(roles__current=True, roles__state=state, roles__role_type=RoleType.senator)\
        .order_by('roles__senator_rank')
    sens = list(sens)

    # Make sure we list at least two slots, filling with Vacant if needed.
    for i in range(2-len(sens)):
        sens.append(None)

    return sens

def get_representatives(state):
    # Load representatives for territories and state at-large districts.
    if stateapportionment[state] in ("T", 1):
        dists = [0]
            
    # Load representatives for non-at-large states.
    else:
        dists = range(1, stateapportionment[state]+1)
    
    reps = []
    for i in dists:
        try:
            reps.append((i, Person.objects.get(roles__current=True, roles__state=state, roles__role_type=RoleType.representative, roles__district=i)))
        except Person.DoesNotExist:
            reps.append((i, None))

    return reps

@anonymous_view
@render_to('person/state.html')
def browse_state(request, state):
    state = normalize_state_arg(state)
    if state not in stateapportionment: raise Http404()
            
    return {
        "state": state,
        "stateapp": stateapportionment[state],
        "statename": statenames[state],
        "senators": get_senators(state),
        "representatives": get_representatives(state),
    }

@anonymous_view
@render_to('person/district_map.html')
def browse_district(request, state, district):
    state = normalize_state_arg(state)
    if state not in stateapportionment: raise Http404()

    # make district an integer
    try:
        district = int(district)
    except ValueError:
        raise Http404()

    # check that the district is in range
    if stateapportionment[state] in ("T", 1):
        # territories and state-at large districts have no page here
        raise Http404()
    elif district < 1 or district > stateapportionment[state]:
        # invalid district number
        raise Http404()
    
    # senators
    sens = [({}, s) for s in get_senators(state)]
    if len(sens) > 0:
        sens[0][0]["first_senator"] = True

    # representatives
    try:
        reps = [({}, Person.objects.get(roles__current=True, roles__state=state, roles__role_type=RoleType.representative, roles__district=district))]
    except Person.DoesNotExist:
        reps = [({}, None)] # vacant
    if len(reps) > 0:
        reps[0][0]["first_representative"] = True

    # map center
    center_lat, center_long, center_zoom = get_district_bounds(state, district)
            
    return {
        "center_lat": center_lat,
        "center_long": center_long,
        "center_zoom": center_zoom,
        "state": state,
        "stateapp": stateapportionment[state],
        "statename": statenames[state],
        "district": int(district),
        "district_zero": ("%02d" % int(district)),
        "statelist": statelist,
        "legislators": sens+reps,
        "MAPBOX_ACCESS_TOKEN": settings.MAPBOX_ACCESS_TOKEN,
    	"MAPBOX_MAP_STYLE": settings.MAPBOX_MAP_STYLE,
    	"MAPBOX_MAP_ID": settings.MAPBOX_MAP_ID,
    }
    
def get_district_bounds(state, district):
    zoom_info_cache_key = "map_zoom_%s-%s" % (state, "" if not district else district)

    if state == "MP":
        return (15.1, 145.7, 11.0)
    elif state == "AS":
        center_long, center_lat, center_zoom = (-170.255127, -14.514462, 8.0)
    elif state == "HI" and district in (None, 0):
        center_long, center_lat, center_zoom = (-157, 20, 7.0)
    elif state == "AK":
        # Alaska has a longitude wrap-around problem so it's easier to just specify
        # the coordinates manually than to figure out generically how to do the math
        # of taking the average of the bounding box coordinates.
        center_long, center_lat, center_zoom = (-150, 63, 4.0)
    elif cache.get(zoom_info_cache_key):
        center_lat, center_long, center_zoom = cache.get(zoom_info_cache_key)
    else:
        with open("static/js/congressional-districts-bboxes-115-2016.js") as f:
            data_json = f.read().replace("var bboxes = ", "")
            data = json.loads(data_json)
        key = state + (("%02d" % district) if district else "")
        left, bottom, right, top = data[key]
        center_lat = (top+bottom)/2
        center_long = (left+right)/2
        center_zoom = min( log(180/(top-bottom))/log(2), log(360/(right-left))/log(2) ) + 1
        cache.set(zoom_info_cache_key, (center_lat, center_long, center_zoom) )
    return (center_lat, center_long, center_zoom)

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
    
    return {
        "statelist": statelist,
        "senate_by_party": get_current_members(RoleType.senator, False, True),
        "senate_vacancies": 100-get_current_members(RoleType.senator, False, False),
        "house_by_party": get_current_members(RoleType.representative, False, True),
        "house_vacancies": 435-get_current_members(RoleType.representative, False, False),
        "house_delegate_vacancies": 6-get_current_members(RoleType.representative, True, False),
    }

@anonymous_view
@render_to('person/district_map_embed.html')
def districtmapembed(request):
    return {
        "demo": "demo" in request.GET,
        "hide_footer": "demo" in request.GET or "footer" in request.GET,
        "state": request.GET.get("state", ""),
        "district": request.GET.get("district", ""),
        "bounds": request.GET.get("bounds", None),
        "MAPBOX_ACCESS_TOKEN": settings.MAPBOX_ACCESS_TOKEN,
    	"MAPBOX_MAP_STYLE": settings.MAPBOX_MAP_STYLE,
    	"MAPBOX_MAP_ID": settings.MAPBOX_MAP_ID,
    }
    
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
                for district in range(1, stateapportionment[state]+1):
                    ret.append( (state, district) )
        return ret
    def location(self, item):
        return "/congress/members/" + item[0] + ("/"+str(item[1]) if item[1] else "")

def session_stats_period(session, stats):
    if not stats['meta']['is_full_congress_stats']:
        return session
    else:
        from django.contrib.humanize.templatetags.humanize import ordinal
        return "the %s Congress" % ordinal(stats['meta']['congress'])
        
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

    # mark the role as current if the logical end date is in the future, to fix the display of Served/Serving
    role.current = (role.logical_dates()[1] > datetime.now().date())

    # clean and sort the stats for this person so they're ready for display
    from person.views_sessionstats import clean_person_stats
    clean_person_stats(stats)

    # group into an order for navigation
    nav_groups = []
    for stat in stats["stats"]:
        for group in nav_groups:
            if group["icon"] == stat["icon"]:
                group["stats"].append(stat)
                break
        else:
            nav_groups.append({ "icon": stat["icon"], "stats": [stat]  })

    import dateutil.parser
    from person.types import Gender, RoleType

    # what dates specifically for the congress?
    (period_min, period_max) = get_congress_dates(stats["meta"]["congress"])
    period_min = max(period_min, role.logical_dates()[0])
    period_max = min(period_max, role.logical_dates()[1])

    return {
        "publishdate": dateutil.parser.parse(stats["meta"]["as-of"]),
        "period": session_stats_period(session, stats),
        "congress_dates": (period_min, period_max),
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
@render_to('person/person_session_stats_overview.html')
def person_session_stats_overview(request, session, cohort, specific_stat):
    from person.views_sessionstats import get_cohort_name, stat_titles

    try:
        stats = Person.load_session_stats(session)
    except ValueError:
        # no stats
        raise Http404()

    if specific_stat is not None and specific_stat not in stat_titles:
        # no stats
        raise Http404()

    try:
        cohort_title = get_cohort_name(cohort, True) if cohort else None
    except ValueError: 
        # invalid URL
        raise Http404()

    # Get all of the cohorts in the data.
    cohorts = { }
    cohort_keys = set()
    for person in stats["people"].values():
        for c in person["cohorts"]:
            c = c["key"]
            cohorts[c] = cohorts.get(c, 0) + 1
            cohort_keys.add(c)
    cohorts = [ (-v, k, get_cohort_name(k, True), v) for k,v in cohorts.items() if "delegation" not in k and v > 10]
    cohorts = sorted(cohorts)

    # Gather data.
    metrics = { }
    for pid, person in stats["people"].items():
        try:
            personobj = Person.objects.get(id=int(pid))
        except:
            # debugging
            continue

        for stat, statinfo in person["stats"].items():
            if specific_stat is not None and stat != specific_stat: continue

            for cohort_key, context in statinfo.get("context", {}).items():
                # filter by cohort, if we're doing that
                if cohort is not None and cohort != cohort_key: continue
                if cohort is None and cohort_key not in ("house", "senate"): continue

                # create an entry for this statistic
                metrics.setdefault(stat, {
                    "key": stat,
                    "title": stat_titles[stat]["title"],
                    "superlatives": stat_titles[stat]["superlatives"],
                    "icon": stat_titles[stat]["icon"],
                    "contexts": { }
                })
                metrics[stat]["title"] = metrics[stat]["title"].replace("{{other_chamber}}", "Other Chamber")
                metrics[stat]["contexts"].setdefault(cohort_key, {
                    "key": cohort_key,
                    "title": get_cohort_name(cohort_key, True),
                    "N": context["N"],
                    "people": ([], []),
                    })

                # if this person ranks #1, #2, #3, fill him in
                c = metrics[stat]["contexts"][cohort_key]["people"]
                if specific_stat is not None:
                    c[0].append( (context["rank_descending"], statinfo["value"], personobj) )
                elif context["rank_ties"] <= 3:
                    if context["rank_ascending"] < 3:
                        c[1].append( (context["rank_descending"], statinfo["value"], personobj) )
                    elif context["rank_descending"] < 3:
                        c[0].append( (context["rank_descending"], statinfo["value"], personobj) )


    metrics = sorted(metrics.values(), key = lambda m : m["title"])

    for m in metrics:
        m["contexts"] = sorted(m["contexts"].values(), key = lambda c : -c["N"])
        for c in m["contexts"]:
            c["people"][0].sort()
            c["people"][1].sort()

    import dateutil.parser
    return {
        "session": session,
        "period": session_stats_period(session, stats),
        "meta": stats["meta"],
        "metrics": metrics,
        "cohorts": cohorts,
        "cohort": cohort,
        "cohort_title": cohort_title,
        "specific_stat": specific_stat,
        "specific_stat_title": stat_titles[specific_stat]["title"].replace("{{other_chamber}}", "Other Chamber") if specific_stat else None,
        "publishdate": dateutil.parser.parse(stats["meta"]["as-of"]),
    }

@anonymous_view
def person_session_stats_export(request, session, cohort, statistic):
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
        if "context" not in person_stats["stats"][statistic]: continue
        rows.append([
            person_stats["stats"][statistic]["context"][cohort]["rank_ascending"],
            person_stats["stats"][statistic]["context"][cohort]["rank_descending"],
            person_stats["stats"][statistic]["context"][cohort]["percentile"],
            person_stats["stats"][statistic]["value"],
            int(person_id),
			"", # bioguide ID
            int(person_stats["role_id"]),
            "", # state
            "", # district
            ])
    if len(rows) == 0:
        raise Http404()

    # assign sortname to the 2nd column so we can use it in sorting
    people = Person.objects.in_bulk([r[4] for r in rows])
    roles = PersonRole.objects.in_bulk([r[6] for r in rows])
    for r in rows:
        #if r[4] not in people: continue # database mismatch, happens during testing
        r[5] = people[r[4]].bioguideid
        r[6], r[7] = roles[r[6]].state, roles[r[6]].district if isinstance(roles[r[6]].district, int) else ""
        r[8] = people[r[4]].lastname.encode("utf-8")

    # sort by rank, then by name
    rows.sort(key = lambda r : (r[0], r[8]))

    # format CSV
    import csv, io
    outfile = io.StringIO()
    writer = csv.writer(outfile)
    writer.writerow(["rank_from_low", "rank_from_high", "percentile", statistic, "id", "bioguide_id", "state", "district", "name"])
    for row in rows: writer.writerow(row)
    output = outfile.getvalue()

    # construct response
    if request.GET.get("inline") is None:
        r = HttpResponse(output, content_type='text/csv')
        r['Content-Disposition'] = 'attachment; filename=' + "govtrack-stats-%s-%s-%s.csv" % (session, cohort, statistic)
    else:
        r = HttpResponse(output, content_type='text/plain')
    return r

@anonymous_view
@render_to('person/person_cosponsors.html')
def person_cosponsors(request, pk):
    # Load the cosponsors.
    from bill.models import Cosponsor
    person = get_object_or_404(Person, pk=pk)
    cosponsors = Cosponsor.objects.filter(bill__sponsor=person, withdrawn=None)\
       .prefetch_related("bill", "bill__terms", "person", "person__roles")

    # Pre-fetch all of the top-terms.
    from bill.models import BillTerm
    top_terms = set(BillTerm.get_top_term_ids())

    # Aggregate.
    total = 0
    from collections import defaultdict
    ret = defaultdict(lambda : {
        "total": 0,
        "by_issue": defaultdict(lambda : 0),
    })
    for cosp in cosponsors:
        total += 1
        ret[cosp.person]["total"] += 1
        for t in cosp.bill.terms.all():
           if t.id in top_terms:
               ret[cosp.person]["by_issue"][t] += 1
        if "first_date" not in ret[cosp.person] or cosp.joined < ret[cosp.person]["first_date"]: ret[cosp.person]["first_date"] = cosp.joined
        if "last_date" not in ret[cosp.person] or cosp.joined > ret[cosp.person]["last_date"]: ret[cosp.person]["last_date"] = cosp.joined

    # Sort.
    for info in ret.values():
        info['by_issue'] = sorted(info['by_issue'].items(), key = lambda kv : kv[1], reverse=True)
    ret = sorted(ret.items(), key = lambda kv : (kv[1]['total'], kv[1]['last_date'], kv[0].sortname), reverse=True)

    # Total bills, date range.
    from bill.models import Bill
    total_bills = Bill.objects.filter(sponsor=person).count()
    date_range = (None, None)
    if len(ret) > 0:
        date_range = (min(r["first_date"] for p, r in ret), max(r["last_date"] for p, r in ret))

    return {
        "person": person,
        "cosponsors": ret,
        "total": total,
        "total_bills": total_bills,
        "date_range": date_range,
    }



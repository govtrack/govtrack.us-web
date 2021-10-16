# -*- coding: utf-8 -*-
import os, os.path
from datetime import datetime, timedelta
from math import log, sqrt

from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
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
"a": "c<u>a</u>t", "b": "<u>b</u>at",
"ah": "c<u>al</u>m", "ch": "<u>ch</u>in",
"air": "h<u>air</u>", "d": "<u>d</u>ay",
               "f": "<u>f</u>un",
"aw": "l<u>aw</u>", "g": "<u>g</u>et",
"ay": "s<u>ay</u>", "h": "<u>h</u>at",
"e": "b<u>e</u>d", "j": "<u>j</u>am",
"eh": "b<u>e</u>d", "k": "<u>k</u>ing",
"ee": "m<u>ee</u>t", "l": "<u>l</u>eg",
"er": "h<u>er</u>", "m": "<u>m</u>an",
"ew": "f<u>ew</u>", "n": "<u>n</u>ot",
"i": "p<u>i</u>n", "ng": "si<u>ng</u>",
"ih": "p<u>i</u>n",
"ī": "<u>eye</u>", "nk": "tha<u>nk</u>",
"o": "t<u>o</u>p", "p": "<u>p</u>en",
"oh": "m<u>o</u>st", "r": "<u>r</u>ag",
"oo": "s<u>oo</u>n", "s": "<u>s</u>it", "ss": "mi<u>ss</u>",
"oor": "p<u>oor</u>", "t": "<u>t</u>op",
"or": "c<u>or</u>n", "th": "<u>th</u>in",
"ow": "c<u>ow</u>", "t͡h": "<u>th</u>is",
"oy": "b<u>oy</u>", "v": "<u>v</u>an",
"u": "c<u>u</u>p", "w": "<u>w</u>ill",
"uh": "c<u>u</u>p", "y": "<u>y</u>es",
"uu": "b<u>oo</u>k", "z": "<u>z</u>ebra",
"zh": "vi<u>s</u>ion",
" ": None, "-": None,
}

vp_2020_candidate_ids = (
  412242, # Klobuchar
  412542, # Warren
  412678, # Harris
  412533, # Duckworth
  412696, # Demings
  412681, # Cortez Masto
  412558, # Lujan Grisham
  400013, # Baldwin
)

prez_2020_candidate_ids = (
  300008, # Biden
  412223, # Gillibrand
  400357, # Sanders
  412678, # Harris
  412542, # Warren
  412598, # Booker
  412242, # Klobuchar
  412514, # Swalwell
  412532, # Gabbard
  400352, # Ryan
  412632, # Moulton
  412575, # O'Rourke
  412544, # Delaney
  404738, # Gravel
  400193, # Inslee
  412330, # Bennet
)

# Kraken Caucus
# -------------
# Representatives who joined the December 2020 Texas v Pennsylvania et al
# Supreme Court case asking to invalidate the electors in GA, MI, PA, and WI.
# https://projects.propublica.org/represent/members/trump-texas-amicus-house-members
# https://www.supremecourt.gov/DocketPDF/22/22O155/163550/20201211132250339_Texas%20v.%20Pennsylvania%20Amicus%20Brief%20of%20126%20Representatives%20--%20corrected.pdf
TexasVPennsylvaniaAmicus = { 400004, 400046, 400052, 400057, 400108, 400158, 400220, 400341, 400376, 400433, 400640, 400643, 400651, 400655, 400656, 400659, 412190, 412191, 412213, 412217, 412226, 412250, 412255, 412256, 412261, 412292, 412295, 412309, 412317, 412395, 412400, 412410, 412417, 412434, 412437, 412443, 412444, 412445, 412460, 412463, 412465, 412472, 412476, 412477, 412480, 412485, 412510, 412525, 412531, 412538, 412548, 412550, 412564, 412568, 412569, 412572, 412574, 412578, 412596, 412601, 412608, 412610, 412619, 412622, 412623, 412624, 412625, 412629, 412630, 412634, 412639, 412641, 412646, 412648, 412655, 412660, 412662, 412670, 412673, 412674, 412683, 412690, 412691, 412692, 412700, 412702, 412703, 412704, 412705, 412706, 412709, 412712, 412724, 412726, 412735, 412736, 412738, 412745, 412746, 412748, 412764, 412765, 412766, 412773, 412777, 412778, 412788, 412792, 412793, 412796, 412811, 412812, 412813, 412815, 412817, 412818, 412819, 412820, 412822, 412823, 412832, 412837, 412843, 412844, 412845, 456791 }
#
# Representatives and senators who voted on Jan 6, 2021 to discount the state electors
# from Arizona and Pennsylvania. (https://www.govtrack.us/congress/votes/117-2021/s1,
# https://www.govtrack.us/congress/votes/117-2021/h10, https://www.govtrack.us/congress/votes/117-2021/s2,
# https://www.govtrack.us/congress/votes/117-2021/h11).
KrakenObjectedToAZPA = {412673, 412675, 412679, 412683, 412690, 412691, 412692, 412698, 412190, 412191, 412704, 412702, 412705, 412706, 412709, 412712, 400433, 412722, 412724, 412213, 412726, 412217, 412735, 412226, 412738, 412743, 412745, 412746, 412748, 456791, 456792, 456793, 456796, 412766, 456799, 456800, 456801, 412255, 412261, 412773, 456805, 456806, 412777, 456807, 456808, 456809, 456813, 456814, 412778, 412788, 456820, 456823, 456824, 412793, 456827, 412796, 456828, 456830, 456833, 456834, 400004, 412292, 456837, 412294, 456841, 456842, 412811, 412812, 412813, 456844, 412815, 456845, 412817, 412818, 412819, 456846, 412309, 412822, 412823, 456847, 456848, 456853, 456855, 456852, 412317, 456850, 412832, 412837, 412838, 412840, 412843, 412844, 412845, 400052, 400057, 400068, 400071, 400077, 412395, 400108, 412397, 412399, 412400, 412410, 400643, 400651, 412434, 412443, 412444, 412445, 400158, 412460, 412463, 412465, 412472, 412476, 412477, 400196, 412485, 412510, 400247, 412538, 412550, 412568, 412569, 412572, 412573, 412574, 412578, 412581, 400297, 412596, 412608, 412622, 412623, 412624, 412625, 400340, 400341, 412629, 412631, 412641, 412646, 412648, 400367, 412655, 412662}
#
# Senators who joined the Jan. 2. 2021 Ted Cruz letter announcing their intent
# to "object" to the electors from "disputed states" (https://www.cruz.senate.gov/?p=press_release&id=5541)
# plus Sen. Hawley who separately announced he would object to at least Pennsylvania's electors
# (https://www.hawley.senate.gov/sen-hawley-will-object-during-electoral-college-certification-process-jan-6)
# and Loeffler (https://twitter.com/KLoeffler/status/1346230542115745793).
KrakenAnnouncedObjection = { 412573, 412496, 412464, 412549, 412679, 400032, 412839, 412294, 412704, 456798, 456796, 412840, 456790 }
#
KrakenCaucus = TexasVPennsylvaniaAmicus | KrakenObjectedToAZPA | KrakenAnnouncedObjection
#
# And the non-Kraken Caucus members...
# All Republicans representatives serving on Dec 11, 2020 that did not join the
# Texas v Pennsylvania amicus.
NTCaucus = [412723, 400029, 400068, 400071, 400077, 400157, 400219, 400247, 400297, 400340, 400365, 400373, 400380, 400404, 400411, 400414, 400419, 400440, 400644, 400654, 412196, 412278, 412302, 412310, 412393, 412394, 412397, 412399, 412402, 412405, 412416, 412421, 412427, 412461, 412486, 412487, 412500, 412503, 412536, 412539, 412541, 412553, 412566, 412581, 412609, 412631, 412649, 412654, 412661, 412664, 412675, 412676, 412698, 412699, 412710, 412713, 412721, 412722, 412731, 412732, 412740, 412747, 412779, 412794, 412807, 412816, 412821, 412826, 412831, 412836, 456792, 456793]


@anonymous_view
@render_to('person/person_details.html')
def person_details(request, pk):
    def build_info():
        if re.match(r"\d", pk):
            person = get_object_or_404(Person, pk=pk)
        else:
            # support bioguide IDs for me
            person = get_object_or_404(Person, bioguideid=pk)

        # There are some people in the database --- presidents and vice presidents --- who have never served in Congress.
        # We don't have any inbound links to those pages, so don't serve them.
        if not person.roles.filter(role_type__in=(RoleType.representative, RoleType.senator)).exists():
            raise Http404()

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
            if role.website: links.append(("%s's Official Website" % person.lastname, role.website, "fas fa-external-link-alt"))
            if person.twitterid: links.append(("@" + person.twitterid, "http://twitter.com/" + person.twitterid, "fab fa-twitter"))
        if person.osid: links.append(("OpenSecrets", "http://www.opensecrets.org/politicians/summary.php?cid=" + person.osid, "fas fa-money-check"))
        if person.pvsid: links.append(("VoteSmart", "http://votesmart.org/candidate/" + person.pvsid, "fa fa-th-list"))
        if person.bioguideid: links.append(("Bioguide", "http://bioguide.congress.gov/scripts/biodisplay.pl?index=" + person.bioguideid, "fa fa-user"))
        if person.cspanid: links.append(("C-SPAN", "http://www.c-spanvideo.org/person/" + str(person.cspanid), "fab fa-youtube"))

        # Get a break down of the top terms this person's sponsored bills fall into,
        # looking only at the most recent five years of bills.
        from bill.models import BillTerm
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

        # Get their enacted bills.
        enacted_bills_src_qs = person.sponsored_bills.exclude(original_intent_replaced=True).order_by('-current_status_date')

        # Get voter info guide for their upcoming election.
        office_id = role.get_office_id()
        if isinstance(office_id, tuple): office_id = "_".join(str(k) for k in office_id)
        election_id = office_id
        if not role.is_up_for_election(): election_id = None
        # Hard-code Joe Biden so we show election guides.
        if person.id == 300008 and str(settings.CURRENT_ELECTION_DATE) == "2020-11-03": election_id = "president"

        # Which Kraken Caucus events did this person take part in?
        kraken_caucus = set()
        if person.id in TexasVPennsylvaniaAmicus: kraken_caucus.add("TexasVPennsylvaniaAmicus")
        if person.id in KrakenObjectedToAZPA: kraken_caucus.add("KrakenObjectedToAZPA")
        if person.id in KrakenAnnouncedObjection: kraken_caucus.add("KrakenAnnouncedObjection")

        # For legislators not in the Kraken caucus, we'll report their
        # affinity to it via cosponsorship.
        ck = "kraken_cosponsors"
        kraken_cosponsors = cache.get(ck)
        if not kraken_cosponsors:
            # Comparisons are hard over uneven time periods, so we'll
            # only look at legislation this Congress.
            from collections import Counter
            from bill.models import Cosponsor
            kraken_cosponsors = Counter(
                Cosponsor.objects
                .filter(
                    bill__congress=CURRENT_CONGRESS,
                    bill__sponsor_id__in=KrakenCaucus,
                    withdrawn=None)
                .values_list("person", flat=True))
            cache.set(ck, kraken_cosponsors, 86400) # one day

        return {'person': person,
                'role': role,
                'active_role': active_role,
                'active_congressional_role': active_role and role.role_type in (RoleType.senator, RoleType.representative),
                'pronunciation': load_pronunciation_key(person),
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
                'is_2020_candidate': person.id in prez_2020_candidate_ids,
                'maybe_vp_candidate':person.id in vp_2020_candidate_ids,
                'election_guides': load_election_guides(election_id) if election_id else None,
                'kraken_caucus': kraken_caucus,
                'kraken_cosponsors': kraken_cosponsors.get(person.id, 0),
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

def load_pronunciation_key(person):
        global pronunciation_guide

        # Load pronunciation from guide. Turn into a mapping from GovTrack IDs to data.
        if pronunciation_guide is None:
            import rtyaml
            if not hasattr(settings, 'PRONUNCIATION_DATABASE_PATH'):
                # debugging
                pronunciation_guide = { }
            else:
                pronunciation_guide = { p["id"]["govtrack"]: p for p in rtyaml.load(open(settings.PRONUNCIATION_DATABASE_PATH)) }

        # Get this person's entry.
        pronunciation = pronunciation_guide.get(person.id)

        # TODO: Validate that the 'name' in the guide matches the name we're actually displaying.

        if pronunciation and not pronunciation.get("key"):
          # Show a key to the letters used in the pronunciation guide. Break apart the name
          # into words which we'll show in columns.
          pronunciation["key"] = []
          for namepart in pronunciation["respell"].split(" // "):
            for nameword in namepart.split(" "):
                # Parse out the symbols actually used in the guide. Sweep from left to right chopping
                # off valid respelling letter combinations, chopping off the longest one where possible.
                pronunciation["key"].append([])
                i = 0
                while i < len(nameword):
                  for s in sorted(pronunciation_guide_key, key = lambda s : -len(s)):
                    if nameword[i:i+len(s)] in (s, s.upper()):
                      pronunciation["key"][-1].append( (nameword[i:i+len(s)], pronunciation_guide_key[s]) )
                      i += len(s)
                      break
                  else:
                    # respelling did not match any valid symbol, should be an error but we don't
                    # want to issue an Oops! for this
                    break

        return pronunciation


def load_key_votes(person):
    # Get this person's key votes.

    import csv
    from vote.models import Vote, Voter

    # First get all of the major votes that this person has participated in.
    all_votes = person.votes.filter(vote__category__in=Vote.MAJOR_CATEGORIES)

    # Then get the unique set of Congress numbers that those votes were in.
    congresses = sorted(set(all_votes.values_list("vote__congress", flat=True).distinct()), reverse=True)

    # And the vote IDs.
    all_votes = all_votes.values_list("vote__id", flat=True)

    # We'll pick top votes where the person was an outlier (so the vote was informative
    # for this Member) and top where the person wasn't an outlier but it had a lot of
    # outliers (so the vote was interesting). Load them all in.
    nonoutlier_votes = { }
    outlier_votes = set()
    for congress in congresses:
        fn = "data/analysis/by-congress/%d/notable_votes.csv" % congress
        if not os.path.exists(fn): continue
        for vote in csv.DictReader(open(fn)):
            if int(vote["vote_id"]) not in all_votes: continue # only look at major votes
            outliers = set(int(v) for v in vote["outliers"].split(" ") if v != "") # person IDs of outliers for this vote
            nonoutlier_votes[int(vote["vote_id"])] = len(outliers) # vote with a lot of outliers
            if person.id in outliers: outlier_votes.add(int(vote["vote_id"])) # vote where the person is an outlier

    votes = []

    # For the non-outlier votes, take those with the most outliers.
    nonoutlier_votes = sorted(nonoutlier_votes.items(), key=lambda kv : -kv[1])
    votes += [kv[0] for kv in nonoutlier_votes[0:4]]

    # For the outlier votes, take some with the most and fewest outliers (i.e. this legislator is most unique).
    votes += [kv[0] for kv in [kv for kv in nonoutlier_votes if kv[0] in outlier_votes][0:4]]
    nonoutlier_votes = sorted(nonoutlier_votes, key=lambda kv : kv[1])
    votes += [kv[0] for kv in [kv for kv in nonoutlier_votes if kv[0] in outlier_votes][0:4]]

    # Convert to Vote objects, make unique, and order by vote date.
    votes = Vote.objects.filter(id__in=votes)
    votes = sorted(votes, key = lambda v : v.created, reverse=True)

    # Replace with a tuple of the vote and the Voter object for this person.
    voters = { v.vote_id: v for v in Voter.objects.filter(vote__in=votes, person=person).select_related("option") }
    votes = [
        (vote, voters[vote.id])
        for vote in votes
    ]

    return votes

def load_election_guides(election_id):
    import csv
    if not os.path.exists("person/election_guides.csv"): return
    for rec in csv.DictReader(open("person/election_guides.csv")):
        if rec["office"] == election_id:
            yield rec

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

def http_rest_json(url, args=None, method="GET", headers={}):
    # Call a REST API that returns a JSON object/array and return it as a Python dict/list.
    import urllib.request, urllib.parse, json
    if method == "GET" and args != None:
        url += "?" + urllib.parse.urlencode(args).encode("utf8")
    req = urllib.request.Request(url, headers=headers)
    r = urllib.request.urlopen(req, timeout=10)
    if r.getcode() != 200: raise Exception("Failed to load: " + url)
    r = r.read().decode("utf8")
    return json.loads(r)

def http_rest_yaml(url, args=None, method="GET", headers={}):
    # Call a REST API that returns a YAML object/array and return it as a Python dict/list.
    import urllib.request, urllib.parse, json
    if method == "GET" and args != None:
        url += "?" + urllib.parse.urlencode(args).encode("utf8")
    req = urllib.request.Request(url, headers=headers)
    r = urllib.request.urlopen(req, timeout=10)
    if r.getcode() != 200: raise Exception("Failed to load: " + url)
    import rtyaml
    return rtyaml.load(r)

@anonymous_view
@render_to('person/district_map.html')
def browse_map(request):
    # Get current members of Congress to show in the district popups.
    current_members = PersonRole.objects.filter(current=True, role_type=RoleType.representative).select_related("person")
    return {
        "statelist": statelist,
        "current_members": current_members,
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
        "end_of_congress_date": get_congress_dates(CURRENT_CONGRESS)[1],
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

    return {
        "state": state,
        "stateapp": stateapportionment[state],
        "statename": statenames[state],
        "district": int(district),
        "district_zero": ("%02d" % int(district)),
        "statelist": statelist,
        "legislators": sens+reps,
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
        with open(settings.DISTRICT_BBOXES_FILE) as f:
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
    # Get the approximate median population of a congressional district.
    # Without using actual congressional district populations, we'll instead
    # divide each state's current population by its number of districts, then
    # repeat that state mean population for each of its districts, combine those
    # lists across all states, and then take the median.
    import numpy
    from vote.models import get_state_population_in_year
    state_population = get_state_population_in_year(datetime.now().year)
    district_median_population = int(round(numpy.median(sum(
      [ [state_population[state]/app] * app
        for state, app in stateapportionment.items()
        if app != "T"],
    [])), -4))

    # We can also get the population of the smallest and largest states
    # in millions.
    min_state_pop = round(min(state_population[state] for state, app in stateapportionment.items() if app != "T") / 1000000, 1)
    max_state_pop = int(round(max(state_population[state] for state, app in stateapportionment.items() if app != "T") / 1000000))

    # Get list of current members by role type --- including or excluding delegates and
    # possibly grouping by party.
    def get_current_members(role_type, delegates, by_party):
        qs = PersonRole.objects.filter(
            role_type=role_type,
            current=True,
            state__in=set(s for s, t in stateapportionment.items() if (t != "T") ^ delegates)
            )
        if not by_party:
            return qs.count()

        # Count legislators by party. The order is used to determine the majority party
        # in each chamber, which needs to also account for independents who caucus with
        # a party because starting on Jan 20, 2021 that affects which is the majority!
        counts_by_party = { r["party"]: { "party": r["party"],
                                          "count": r["count"],
                                          "caucus_parties": { },
                                          "vp": False }
                            for r in qs.filter(caucus=None).values('party').annotate(count=Count('party')) }
        for r in qs.exclude(caucus=None).values('caucus', 'party').annotate(count=Count('caucus')).order_by('-count'):
            pp = counts_by_party[r["caucus"]]
            pp["count"] += r["count"]
            pp["caucus_parties"][r["party"]] = r["count"]

        # In addition, the Senate majority party may depend on the vice president's party.
        if role_type == RoleType.senator:
            vp = PersonRole.objects.filter(
                  role_type=RoleType.vicepresident,
                  current=True
                 ).first()
            if vp:
                counts_by_party[vp.party]["vp"] = True

        # Now sort the parties in majority-minority order. Break ties with the VP flag.
        counts_by_party = sorted(counts_by_party.values(), key = lambda pp : (
            pp["count"],
            pp["vp"]
        ), reverse=True)

        return counts_by_party

    # Check senate majority party percent vs apportioned total state population of total population
    # in states + DC (because that's the population data we have).
    majority_party = get_current_members(RoleType.senator, False, True)[0]["party"]
    current_senators = PersonRole.objects.filter(current=True, role_type=RoleType.senator)
    state_totals = { state: len([p for p in current_senators if p.state == state]) for state in set(p.state for p in current_senators)}
    majority_party_senators_proportion = len([p for p in current_senators if p.party == majority_party]) / current_senators.count()
    majority_party_apportioned_population = sum(state_population[p.state]/state_totals[p.state] for p in current_senators if p.party == majority_party)
    total_state_population = sum(state_population[state] for state in state_population)
    majority_party_apportioned_population_proportion = majority_party_apportioned_population / total_state_population
    if int(round(majority_party_senators_proportion*100)) <= int(round(majority_party_apportioned_population_proportion*100)):
        # Not interesting.
        majority_party_apportioned_population_proportion = None
    else:
        majority_party_apportioned_population_proportion = round(majority_party_apportioned_population_proportion*100, 1)

    return {
        "statelist": statelist,
        "senate_by_party": get_current_members(RoleType.senator, False, True),
        "senate_vacancies": 100-get_current_members(RoleType.senator, False, False),
        "house_by_party": get_current_members(RoleType.representative, False, True),
        "house_vacancies": 435-get_current_members(RoleType.representative, False, False),
        "house_delegate_vacancies": 6-get_current_members(RoleType.representative, True, False),
        "longevity": get_members_longevity_table(),
        "agesex": get_members_age_sex_table(),
        "majority_party_apportioned_population_proportion": majority_party_apportioned_population_proportion,
        "min_state_pop": min_state_pop,
        "max_state_pop": max_state_pop,
        "district_median_population": district_median_population,
    }


def get_members_longevity_table():
    # Get a breakdown of members by chamber and party by longevity. Sum the total number
    # of days in office in Congress by all current members. It's easier to sum without
    # trying to restrict the longevity computation to days in the same chamber.
    from collections import defaultdict
    from datetime import datetime, timedelta

    # Collect the longevity of each member currently serving in Congress.
    now = datetime.now().date()
    longevity_by_member = defaultdict(lambda : timedelta(0))
    for role in PersonRole.objects.filter(person__roles__current=True, role_type__in=(RoleType.senator, RoleType.representative)): # any congressional role for any member who has a current role
        longevity_by_member[role.person] += (min(now, role.enddate) - role.startdate)
    
    # Put each currently serving member into a bucket by chamber, quantized longevity, and party.
    longevity_by_bucket = defaultdict(lambda : defaultdict(lambda : defaultdict(lambda : 0)))
    for role in PersonRole.objects.filter(current=True, role_type__in=(RoleType.senator, RoleType.representative)): # current member roles
        bucket = longevity_by_member[role.person].days // 365.25
        if role.role_type == RoleType.senator:
            bucket_size = 6
        elif role.role_type == RoleType.representative:
            bucket_size = 4
        else:
            raise ValueError()
        bucket = int(bucket // bucket_size)
        bucket = (-bucket, "{}-{} years".format(bucket*bucket_size, (bucket+1)*bucket_size-1))
        longevity_by_bucket[role.role_type][bucket][role.party] += 1

    # Get the parties in sorted order by number of members by chamber so we can put the series in order.
    party_order = list(PersonRole.objects.filter(current=True, role_type__in=(RoleType.senator, RoleType.representative)).values('role_type', 'party').annotate(count=Count('party')).order_by('-count'))

    # Reform the data into chamber -> party -> bucket array since each party will be a series with
    # buckets (in correspondence between parties).
    return {
        role_type: {
            "buckets": [bucket_name for (bucket_index, bucket_name), counts in sorted(buckets.items())],
            "series": [
                {
                    "name": rec["party"]+'s',
                    "data": [counts[rec["party"]] for (bucket_index, bucket_name), counts in sorted(buckets.items())],
                    "color": { "Democrat": "#008ed1", "Republican": "#f83631", "Independent": "#921b85" }.get(rec["party"]),
                         # see colors also defined in vote.views.vote_diagram_colors
                }
                for rec in reversed(party_order) if rec["role_type"] == role_type
            ]
        }
        for role_type, buckets in longevity_by_bucket.items()
    }

def get_members_age_sex_table():
    # Compute an age/sex breakdown. For each chamber, compute the median age. Then bucket
    # by chamber, above/below the median age, and sex.
    from datetime import datetime
    from numpy import median
    from person.types import Gender
    now = datetime.now().date()
    ages = PersonRole.objects.filter(current=True, role_type__in=(RoleType.senator, RoleType.representative)).values('role_type', 'person__gender', 'person__birthday')
    for p in ages: # if any legislators are missing a birthday, we can't create the table
        if p['person__birthday'] is None:
            return None
    ages = [(v['role_type'], v['person__gender'], int(round((now-v['person__birthday']).days/365.25))) for v in ages]
    median_age = int(round(median([p[2] for p in ages]))) # get median age across chambers so the two charts are consistent
    def minmax(data): return { "min": min(data), "max": max(data) }
    minmax_age_by_chamber = { role_type: minmax([v[2] for v in ages if v[0] == role_type]) for role_type in (RoleType.senator, RoleType.representative) }
    return {
        role_type: {
            "summary": {
                "age": median_age,
                "percent_older_men": int(round(100 *
                      len([v for v in ages if v[0] == role_type and v[1] == Gender.male and v[2] > median_age])
                    / len([v for v in ages if v[0] == role_type])
                )),
                "percent_younger_women": int(round(100 *
                      len([v for v in ages if v[0] == role_type and v[1] == Gender.female and v[2] <= median_age])
                    / len([v for v in ages if v[0] == role_type])
                ))
            },
            "buckets": [
                "{}-{} years old".format(median_age+1, minmax_age_by_chamber[role_type]["max"]),
                "{}-{} years old".format(minmax_age_by_chamber[role_type]["min"], median_age),
            ],
            "series": [
                {
                    "name": gender_label,
                    "data": [
                        len([v for v in ages if v[0] == role_type and v[1] == gender_value and v[2] > median_age]),
                        len([v for v in ages if v[0] == role_type and v[1] == gender_value and v[2] <= median_age]),
                    ]
                }
                for (gender_label, gender_value) in [
                    ("Men", Gender.male),
                    ("Women", Gender.female),
                ]
            ]
        }
        for role_type in (RoleType.senator, RoleType.representative)
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
    }


@anonymous_view
@json_response
def lookup_reps(request):
    from django.contrib.humanize.templatetags.humanize import ordinal
    from person.name import get_person_name

    # Get the state and district from the query string.
    try:
        state = request.GET['state']
        district = int(request.GET['district'])
        if state not in stateapportionment: raise Exception()
    except:
        return {
        }

    # Get the bill (optional) from the query string
    from bill.models import Bill
    try:
        bill = Bill.from_congressproject_id(request.GET["bill"])
    except:
        bill = None

    # Helper to get relevant committee assignments.
    from committee.models import CommitteeMember, CommitteeMemberRole
    from committee.util import sort_members
    def mention_committees_once(committeeassignments):
        # The committee assignments have been sorted first by role (i.e.
        # committees that the person is the chair of come first) and then
        # by committee name (which also puts subcommittees after committees).
        # In order to be less verbose, only mention each full committee
        # once --- take the first in each mention.
        seen = set()
        for c in committeeassignments:
            if (c.committee in seen) or (c.committee.committee in seen):
                continue
            yield c
            if c.committee.committee is not None:
                seen.add(c.committee.committee) # add main committee
            else:
                seen.add(c.committee) # add this committee

    bounds = get_district_bounds(state, district)
    return {
        "state": {
            "name": statenames[state],
            "isTerritory": stateapportionment[state] == "T",
        },
        "district": {
            "ordinal": ordinal(district) if district > 0 else "At Large",
            "bounds": {
                "center": { "latitude": bounds[0], "longitude": bounds[1] },
                "zoom": bounds[2]
            }
        },
        "members": [
            {
                "id": p.id,
                "name": get_person_name(p, role_recent=True, firstname_position="before", show_title=True, show_party=False, show_district=False),
                "name_formal": p.current_role.get_title() + " " + p.lastname,
                "url": p.get_absolute_url(),
                "type": p.current_role.get_role_type_display(),
                "description": p.current_role.get_description(),
                "party": p.current_role.party,
                "photo_url": p.get_photo_url_50() if p.has_photo() else None,
                "contact_url": (p.current_role.extra or {}).get("contact_form") or p.current_role.website,
                "phone": p.current_role.phone,
                "website": p.current_role.website,
                "pronouns": {
                    "him_her": p.him_her,
                    "his_her": p.his_her,
                    "he_she": p.he_she,
                },
                "bill-status": {
                    "cosponsor": p in bill.cosponsors.all(),
                    "committee-assignments": [
                        {
                            "committee": c.committee.fullname,
                            "role": c.get_role_display() if c.role in (CommitteeMemberRole.chair, CommitteeMemberRole.ranking_member, CommitteeMemberRole.vice_chair) else None,
                        }
                        for c in
                            mention_committees_once(
                             sort_members(
                                CommitteeMember.objects.filter(person=p, committee__in=bill.committees.all())))
                    ]
                } if bill else None,
            }
            for p in
            list(Person.objects.filter(roles__current=True, roles__state=state, roles__role_type=RoleType.senator)
              .order_by('roles__senator_rank'))
            +
            list(Person.objects.filter(roles__current=True, roles__state=state, roles__district=district, roles__role_type=RoleType.representative))
        ]
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

    # get the role as stored in the file and set it on the person object so it affects the name
    person.role = PersonRole.objects.get(id=stats["role_id"])

    # mark the role as current if the logical end date is in the future, to fix the display of Served/Serving
    person.role.current = (person.role.logical_dates()[1] > datetime.now().date())

    # compute a name for this time period
    from person.name import get_person_name
    person.name = get_person_name(person)

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
    period_min = max(period_min, person.role.logical_dates()[0])
    period_max = min(period_max, person.role.logical_dates()[1])

    return {
        "publishdate": dateutil.parser.parse(stats["meta"]["as-of"]),
        "period": session_stats_period(session, stats),
        "congress_dates": (period_min, period_max),
        "person": person,
        "photo": person.get_photo()[0],
        "himher": Gender.by_value(person.gender).pronoun_object,
        "class": RoleType.by_value(person.role.role_type).label.lower() + "s",
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

    # Load people and roles in bulk.
    people = Person.objects.in_bulk({ int(pid) for pid in stats["people"] })
    roles = PersonRole.objects.in_bulk({ person["role_id"] for person in stats["people"].values() })

    # Gather data.
    metrics = { }
    for pid, person in stats["people"].items():
        try:
            personobj = people[int(pid)]
        except:
            # debugging
            continue

        # Compute each person's name for their role.
        from person.name import get_person_name
        personobj.role = roles.get(person["role_id"])
        personobj.name = get_person_name(personobj)

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
            c["people"][0].sort(key = lambda v : (v[0], v[2].sortname)) # sort by rank, then by name
            c["people"][1].sort(key = lambda v : (v[0], v[2].sortname))

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


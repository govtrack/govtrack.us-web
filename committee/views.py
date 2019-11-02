# -*- coding: utf-8 -*-
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.conf import settings

from common.decorators import render_to

from committee.models import Committee, CommitteeMemberRole, CommitteeType, CommitteeMeeting
from committee.util import sort_members
from events.models import Feed

from datetime import datetime

from twostream.decorators import anonymous_view, user_view_for

@anonymous_view
@render_to('committee/committee_details.html')
def committee_details(request, parent_code, child_code=None):
    if child_code:
        if len(child_code) == 2:
            obj = get_object_or_404(Committee, code=parent_code+child_code)
        else: # legacy
            obj = get_object_or_404(Committee, code=child_code)
            return redirect(obj, permanent=True)
        parent = obj.committee
    else:
        obj = get_object_or_404(Committee, code=parent_code)
        parent = None
    members = sort_members(obj.members.all())
    subcommittees = sorted(obj.subcommittees.filter(obsolete=False), key=lambda s : s.name_no_article)
    
    party_counts = { }
    for m in members:
        role = m.person.get_current_role()
        if role: # member left congress but is still listed as committee member
            party_counts[role.party] = party_counts.get(role.party, 0) + 1
    party_counts = sorted(party_counts.items(), key = lambda p : -p[1])
    
    return {'committee': obj,
            'parent': parent,
            'subcommittees': subcommittees,
            'members': members,
            'SIMPLE_MEMBER': CommitteeMemberRole.member,
            'TYPE_JOINT': CommitteeType.joint,
            'feed': obj.get_feed(),
            "member_highlights": [m for m in members if m.role in (CommitteeMemberRole.chair, CommitteeMemberRole.vice_chair, CommitteeMemberRole.ranking_member)],
            "party_counts": party_counts,
            "recent_reports": obj.get_recent_reports(),
            "press_statements": fetch_statements(obj),
            }


@user_view_for(committee_details)
def committee_details_user_view(request, parent_code, child_code=None):
    committee = get_object_or_404(Committee, code=parent_code+(child_code if child_code else ""))

    ret = { }

    from person.views import render_subscribe_inline
    ret.update(render_subscribe_inline(request, committee.get_feed()))

    return ret

@anonymous_view
@render_to('committee/committee_list.html')
def committee_list(request):
    from events.models import Feed
    import re

    def getlist(type_):
        items = list(Committee.objects.filter(committee_type=type_, obsolete=False))
        for c in items:
            if c.name.startswith("Joint "):
                c.display_name = c.name
            else:
                c.display_name = c.sortname()
        return sorted(items, key=lambda c : c.display_name)

    return {
        'senate_committees': getlist(CommitteeType.senate),
        'house_committees': getlist(CommitteeType.house),
        'joint_committees': getlist(CommitteeType.joint),
        'feed': Committee.AllCommitteesFeed(),
        'upcoming_meetings': CommitteeMeeting.objects.filter(when__gte=datetime.now().date()).count(),
    }

   
import django.contrib.sitemaps
class sitemap(django.contrib.sitemaps.Sitemap):
    changefreq = "weekly"
    priority = 1.0
    def items(self):
        return Committee.objects.filter(obsolete=False)

@anonymous_view
@render_to("committee/calendar.html")
def committee_calendar(request):
    committee_meetings = list(CommitteeMeeting.objects.filter(when__gte=datetime.now().date()).order_by()\
        .prefetch_related("committee", "committee__committee"))
    committee_meetings.sort(key = lambda mtg : (mtg.when, mtg.committee.sortname(True)))

    return {
        "committee_meetings": committee_meetings,
        'feed': Committee.AllCommitteesFeed(),
    }

def fetch_statements(committee):
    from person.views import http_rest_json
    from parser.processor import Processor

    # only full committee statements are available
    if committee.committee: # has a parent committee
        return []

    # load statements from ProPublica API, ignoring any network errors
    try:
        statements = http_rest_json(
          "https://api.propublica.org/congress/v1/statements/committees/{committee_id}.json".format(
            committee_id=committee.code,
          ),
          headers={
            'X-API-Key': settings.PROPUBLICA_CONGRESS_API_KEY,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
          })
        if statements["status"] != "OK": raise Exception()
        statements = statements["results"]
    except ValueError:
        return []

    # make simplified statements records
    statements = [{
        "date": Processor.parse_datetime(s["date"]).date(),
        "type": s["statement_type"],
        "title": s["title"],
        "url": s["url"],
    } for s in statements
      if s["date"]]

    # # downcase all-caps titles
    # for s in statements:
    #   if s["title"] != s["title"].upper(): continue
    #   s["title"] = s["title"].lower()
    #   if s["person"]: s["title"] = s["title"].replace(s["person"].lastname.lower(), s["person"].lastname) # common easy case fix

    return statements
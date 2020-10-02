# -*- coding: utf-8 -*-
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.conf import settings

from common.decorators import render_to

from committee.models import Committee, CommitteeMemberRole, CommitteeType, CommitteeMeeting
from committee.util import sort_members
from events.models import Feed

from datetime import timedelta, date, datetime

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

    # Get data on recent committee activity by date so we can display a visualization.
    committee_activity_by_date = { }
    today = datetime.now().date()
    def first_monday_after(d): # d.weekday() is zero if d is a Monday
      return d + timedelta((7-d.weekday()) % 7)
    start_date = first_monday_after(today - timedelta(days=365))
    def daterange(start_date, end_date): # https://stackoverflow.com/a/1060330
        for n in range(int((end_date - start_date).days)):
            yield start_date + timedelta(n)
    for d in list(daterange(start_date, today)):
        if d.weekday() <= 4: # exclude Saturday/Sunday because Congress rarely conducts business then
            committee_activity_by_date[d] = {
                "count": 0,
                "date": d.strftime("%b %d").replace(" 0", " "),
            }
    for cm in CommitteeMeeting.objects.filter(when__gte=start_date).values_list("when", flat=True):
        if cm.date() in committee_activity_by_date:
            committee_activity_by_date[cm.date()]["count"] += 1
    committee_activity_by_date = [v for k, v in sorted(committee_activity_by_date.items())]

    return {
        'senate_committees': getlist(CommitteeType.senate),
        'house_committees': getlist(CommitteeType.house),
        'joint_committees': getlist(CommitteeType.joint),
        'feed': Committee.AllCommitteesFeed(),
        'upcoming_meetings': CommitteeMeeting.objects.filter(when__gte=datetime.now().date()).count(),
        'committee_activity_by_date': committee_activity_by_date,
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
    except:
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

@anonymous_view
@render_to("committee/game.html")
def game(committee):
    from events.models import Feed
    import re
    import random
    from bill.models import Bill, BillType, BillStatus, BillTerm, TermType, BillTextComparison, BillSummary
    from person.models import Person
    from settings import CURRENT_CONGRESS

    #copy load bill from bill views.py
    def load_bill_from_url(congress, type_slug, number):
        try:
            bill_type = BillType.by_slug(type_slug)
        except BillType.NotFound:
            raise Http404("Invalid bill type: " + type_slug)

        return get_object_or_404(Bill, congress=congress, bill_type=bill_type, number=number)

    #come up with a random bill number
    def random_bill():
        types = ['s','hr']
        randomtype = random.randint(0,1)
        type_slug = types[randomtype]
        number = str(random.randint(1,9999))
        try:
            load_bill_from_url(CURRENT_CONGRESS, type_slug, number)
        except:
            return False
        bill = load_bill_from_url(CURRENT_CONGRESS, type_slug, number)
        return bill

    #go fetch the random bill
    def get_random_bill():
        is_bill = False
        while is_bill == False:
            bill = random_bill()
            is_bill = bool(bill)
            if is_bill == True:
                return bill

    #copy get list of committees from committee view.py
    def getlist(type_):
        items = list(Committee.objects.filter(committee_type=type_, obsolete=False))
        for c in items:
            if c.name.startswith("Joint "):
                c.display_name = c.name
            else:
                c.display_name = c.sortname()
        return sorted(items, key=lambda c : c.display_name)

    def getcommittees(bill):
        import json
        from django.core.serializers.json import DjangoJSONEncoder
        actual_committees = []
        items = bill.committees.all()
        for c in items:
            if not c.committee:
                committee = c.code
                actual_committees = actual_committees + [committee]
        committeesJSON = json.dumps(list(actual_committees), cls=DjangoJSONEncoder)
        return committeesJSON

    def numberofcommittees(bill):
        count = 0
        for c in bill.committees.all():
            if not c.committee:
                count += 1
        return count

    bill = get_random_bill()

    return {
    'house_committees': getlist(CommitteeType.house),
    'senate_committees': getlist(CommitteeType.senate),
    'bill': bill,
    'number_of_committees': numberofcommittees(bill),
    'actual_committees': getcommittees(bill),
    }

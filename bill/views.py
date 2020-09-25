# -*- coding: utf-8 -*-
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.conf import settings
from django.contrib.humanize.templatetags.humanize import ordinal
from django.contrib.auth.decorators import login_required
from django.db.models import Count, F
from django.core.cache import cache

from common.decorators import render_to

from bill.models import Bill, BillType, BillStatus, BillTerm, TermType, BillTextComparison, BillSummary
from bill.search import bill_search_manager, parse_bill_citation
from bill.title import get_secondary_bill_title
from committee.util import sort_members
from person.models import Person
from events.models import Feed

from settings import CURRENT_CONGRESS

from us import get_congress_dates

import urllib.request, urllib.parse, urllib.error, urllib.request, urllib.error, urllib.parse, json, datetime, re
from registration.helpers import json_response
from twostream.decorators import anonymous_view, user_view_for

def load_bill_from_url(congress, type_slug, number):
    # not sure why we were trying this
    #if type_slug.isdigit():
    #    bill_type = type_slug
    try:
        bill_type = BillType.by_slug(type_slug)
    except BillType.NotFound:
        raise Http404("Invalid bill type: " + type_slug)

    return get_object_or_404(Bill, congress=congress, bill_type=bill_type, number=number)

def get_related_bills(bill):
    # get related bills
    related_bills = []
    reintro_prev = None
    reintro_next = None
    for reintro in bill.find_reintroductions():
        if reintro.congress < bill.congress: reintro_prev = reintro
        if reintro.congress > bill.congress and not reintro_next: reintro_next = reintro
    if reintro_prev: related_bills.append({ "bill": reintro_prev, "note": "was a previous version of this bill.", "show_title": False })
    if reintro_next: related_bills.append({ "bill": reintro_next, "note": "was a re-introduction of this bill in a later Congress.", "show_title": False })
    for rb in bill.get_related_bills():
        if rb.relation in ("identical", "rule"):
            related_bills.append({ "bill": rb.related_bill, "note": "(%s)" % rb.relation, "show_title": False })
        elif rb.relation == "ruled-by":
            related_bills.append({ "bill": rb.related_bill, "prenote": "Debate on", "note": " is governed by these rules.", "show_title": False })
        else:
            related_bills.append({ "bill": rb.related_bill, "note": ("(%s)" % (rb.relation.title() if rb.relation != "unknown" else "Related")), "show_title": True })
    return related_bills

@anonymous_view
@render_to('bill/bill_details.html')
def bill_details(request, congress, type_slug, number):
    # load bill and text
    bill = load_bill_from_url(congress, type_slug, number)
    text_info = bill.get_text_info(with_citations=True)

    # load stakeholder positions
    from stakeholder.models import BillPosition
    stakeholder_posts = bill.stakeholder_positions\
        .filter(post__stakeholder__verified=True)\
        .select_related("post", "post__stakeholder")\
        .order_by('-created')
    def add_position_return_post(bp): bp.post.position = bp.position; return bp.post
    stakeholder_posts = [add_position_return_post(bp) for bp in stakeholder_posts]

    # context
    return {
        'bill': bill,
        "congressdates": get_congress_dates(bill.congress),
        "subtitle": get_secondary_bill_title(bill, bill.titles),
        "current": bill.congress == CURRENT_CONGRESS,
        "dead": bill.congress != CURRENT_CONGRESS and bill.current_status not in BillStatus.final_status_obvious,
        "feed": bill.get_feed(),
        "prognosis": bill.get_prognosis_with_details(),
        "text_info": text_info,
        "text_incorporation": fixup_text_incorporation(bill.text_incorporation),
        "show_media_bar": not bill.original_intent_replaced and bill.sponsor and bill.sponsor.has_photo() and text_info and text_info.get("has_thumbnail"),
        "stakeholder_posts": stakeholder_posts,
        "legislator_statements": fetch_statements(bill),
    }

@anonymous_view
@render_to('bill/bill_key_questions.html')
def bill_key_questions(request, congress, type_slug, number):
    # load bill and text
    bill = load_bill_from_url(congress, type_slug, number)
    text_info = bill.get_text_info(with_citations=True)

    # load stakeholder positions
    from stakeholder.models import BillPosition
    stakeholder_posts = bill.stakeholder_positions\
        .filter(post__stakeholder__verified=True)\
        .select_related("post", "post__stakeholder")\
        .order_by('-created')
    def add_position_return_post(bp): bp.post.position = bp.position; return bp.post
    stakeholder_posts = [add_position_return_post(bp) for bp in stakeholder_posts]

    # context
    return {
        'bill': bill,
        "congressdates": get_congress_dates(bill.congress),
        "dead": bill.congress != CURRENT_CONGRESS and bill.current_status not in BillStatus.final_status_obvious,
        "prognosis": bill.get_prognosis_with_details(),
        "text_info": text_info,
        "text_incorporation": fixup_text_incorporation(bill.text_incorporation),
        "stakeholder_posts": stakeholder_posts,
        "legislator_statements": fetch_statements(bill),
    }

@user_view_for(bill_key_questions)
def bill_key_questions_user_view(request, congress, type_slug, number):
    bill = load_bill_from_url(congress, type_slug, number)
    ret = { }
    ret["reactions"] = get_user_bill_reactions(request, bill)
    ret["position"] = get_user_bill_position_info(request, bill)
    return ret

def fixup_text_incorporation(text_incorporation):
    if text_incorporation is None:
        return text_incorporation
    def fixup_item(item):
        item = dict(item)
        if item["my_ratio"] * item["other_ratio"] > .9:
            item["identical"] = True
        item["other"] = Bill.from_congressproject_id(item["other"])
        item["other_ratio"] *= 100
        return item
    return list(map(fixup_item, text_incorporation))

def fetch_statements(bill):
    from person.models import Person
    from person.views import http_rest_json
    from parser.processor import Processor

    # load statements from ProPublica API, ignoring any network errors
    try:
        statements = http_rest_json(
          "https://api.propublica.org/congress/v1/{congress}/bills/{bill}/statements.json".format(
            congress=bill.congress,
            bill=bill.bill_type_slug + str(bill.number),
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

    # bulk-fetch all legislators mentioned and make a mapping from bioguide ID to Person object
    legislators = { p.bioguideid: p for p in Person.objects.filter(bioguideid__in=[s['member_id'] for s in statements]) }

    # make simplified statements records
    statements = [{
        "date": Processor.parse_datetime(s["date"]).date(),
        "person": legislators.get(s["member_id"]),
        "type": s["statement_type"],
        "title": s["title"],
        "url": s["url"],
    } for s in statements
      if s["date"]]

    # downcase all-caps titles
    for s in statements:
      if s["title"] != s["title"].upper(): continue
      s["title"] = s["title"].lower()
      if s["person"]: s["title"] = s["title"].replace(s["person"].lastname.lower(), s["person"].lastname) # common easy case fix

    # sort by date because we want to give a diversity of viewpoints by showing only one
    # statement per legislator
    statements.sort(key = lambda s : s["date"], reverse=True)

    # Put all of the statements that are the most recent for the legislator first, then all of the second-most-recent, and so on.
    # Since sort is stable, it will remain in reverse-date order within each group.
    seen = { }
    for s in statements:
      seen[s["person"]] = seen.get(s["person"], 0) + 1
      s["legislator_ordinal"] = seen[s["person"]]
    statements.sort(key = lambda s : s["legislator_ordinal"])

    # bulk-fetch ideology & leadership scores
    from person.models import RoleType
    from person.analysis import load_sponsorship_analysis2
    scores = load_sponsorship_analysis2(bill.congress, RoleType.representative, None)["all"] + load_sponsorship_analysis2(bill.congress, RoleType.senator, None)["all"]
    leadership_scores = {
      s["id"]: float(s["leadership"])
      for s in scores
    }
    ideology_scores = {
      s["id"]: float(s["ideology"])
      for s in scores
    }

    # Tag relevance of the person making the press statement. (We'd love to prioritize relevant
    # committee chairs but we only have current committee info so we couldn't do it for
    # past bills.)
    cosponsors = set(bill.cosponsors.all())
    for s in statements:
      if s["person"] == bill.sponsor:
        s["relevance"] = "Sponsor"
        s["priority"] = (0, -leadership_scores.get(s["person"].id, 0))
      elif s["person"] in cosponsors:
        s["relevance"] = "Co-sponsor"
        s["priority"] = (1, -leadership_scores.get(s["person"].id if s["person"] else 0, 0))

    # Get the prioritized statements to show.
    ret = []

    # For up to the first two, show the sponsor and the cosponsor with the highest leadership
    # score (or if there is no sponsor statement, the two top cosponsors), but prioritizing
    # the most recent statements for each legislator
    statements.sort(key = lambda s : (s["legislator_ordinal"], s.get("priority", (2,))))
    while statements and statements[0].get("priority") and statements[0]["legislator_ordinal"] == 1 and len(ret) < 2:
      ret.append(statements.pop(0))

    # For the third statement, take the legislator with the ideology score furthest from
    # the sponsor's score, to hopefully get an opposing viewpoint.
    if bill.sponsor and bill.sponsor.id in ideology_scores:
      statements.sort(key = lambda s : (
               s["legislator_ordinal"], # most recent statements by legislators first
               not(s["person"] and s["person"].id in ideology_scores), # people with ideology scores first
               "relevance" in s, # people who aren't a sponsor/cosponsor first
               -abs(ideology_scores.get(s["person"].id if s["person"] else 0, 0) - ideology_scores[bill.sponsor.id]) ) )
      while statements and len(ret) < 3:
        ret.append(statements.pop(0))

    return ret


@user_view_for(bill_details)
def bill_details_user_view(request, congress, type_slug, number):
    bill = load_bill_from_url(congress, type_slug, number)

    ret = { }
    if request.user.is_staff:
        admin_panel = """
            {% load humanize %}
            <div class="clear"> </div>
            <div style="margin-top: 1.5em; padding: .5em; background-color: #EEE; ">
                <b>ADMIN</b> - <a href="{% url "bill_go_to_summary_admin" %}?bill={{bill.id}}">Edit Summary</a>
                 | <a href="/admin/bill/bill/{{bill.id}}">Edit</a>
                <br/>Tracked by {{feed.tracked_in_lists.count|intcomma}} users
                ({{feed.tracked_in_lists_with_email.count|intcomma}} w/ email).
            </div>
            """

        from django.template import Template, Context
        ret["admin_panel"] = Template(admin_panel).render(Context({
            'bill': bill,
            "feed": bill.get_feed(),
            }))

    from person.views import render_subscribe_inline
    ret.update(render_subscribe_inline(request, bill.get_feed()))

    ret["reactions"] = get_user_bill_reactions(request, bill)
    ret["position"] = get_user_bill_position_info(request, bill)
    if request.user.is_authenticated:
        ret["stakeholders"] = [ { "id": s.id, "title": s.name } for s in request.user.stakeholder_set.all() ]

    return ret

def get_user_bill_reactions(request, bill):
    import json
    from website.models import Reaction

    # get aggregate counts
    reaction_subject = "bill:" + bill.congressproject_id
    emoji_counts = { }
    for r in Reaction.objects.filter(subject=reaction_subject).values("reaction").annotate(count=Count('id')):
        v = json.loads(r["reaction"])
        if isinstance(v, dict):
            for emoji in v.get("emojis", []):
                emoji_counts[emoji] = emoji_counts.get(emoji, 0) + r["count"]

    # get user's reactions
    r = Reaction.get_for_user(request).filter(subject=reaction_subject).first()
    my_emojis = set()
    if r and isinstance(r.reaction, dict):
        my_emojis = set(r.reaction.get("emojis", []))

    # get all possible emojis
    ret = [ ]
    for emoji in Reaction.EMOJI_CHOICES:
        ret.append({
            "name": emoji,
            "count": emoji_counts.get(emoji, 0),
            "me": emoji in my_emojis,
        })

    # stable sort by count so that zeroes are in our preferred order
    ret = sorted(ret, key = lambda x : -x["count"])

    return ret

def get_user_bill_position_info(request, bill):
    if not request.user.is_authenticated: return None
    # user registered positions
    from website.models import UserPosition
    p = UserPosition.objects.filter(user=request.user, subject=bill.get_feed().feedname).first()
    if p:
        return { "likert": p.likert, "reason": p.reason }
    return None

@anonymous_view
@render_to("bill/bill_summaries.html")
def bill_summaries(request, congress, type_slug, number):
    bill = load_bill_from_url(congress, type_slug, number)
    return {
        "bill_subpage": "Summary",
        "bill": bill,
        "congressdates": get_congress_dates(bill.congress),
        "text_info": bill.get_text_info(with_citations=True), # for the header tabs
    }

@user_view_for(bill_summaries)
def bill_summaries_user_view(request, congress, type_slug, number):
    bill = load_bill_from_url(congress, type_slug, number)
    ret = { }
    ret["reactions"] = get_user_bill_reactions(request, bill)
    ret["position"] = get_user_bill_position_info(request, bill)
    return ret

@anonymous_view
@render_to("bill/bill_full_details.html")
def bill_full_details(request, congress, type_slug, number):
    bill = load_bill_from_url(congress, type_slug, number)
    return {
        "bill_subpage": "Details",
        "bill": bill,
        "related": get_related_bills(bill),
        "text_info": bill.get_text_info(with_citations=True), # for the header tabs
        "cosponsors": get_cosponsors_table(bill),
    }

def get_cosponsors_table(bill):
    # Get all sponsor/cosponsors.
    cosponsors = []
    if bill.sponsor is not None: # historical bills may be missing this
        cosponsors.append({
            "person": bill.sponsor,
            "name": bill.sponsor_name,
            "party": bill.sponsor_role.party if bill.sponsor_role else "Unknown",
            "joined_withdrawn": "Primary Sponsor",
            "sort_cosponsor_type": 0,
            "sort_cospsonsor_date": None,
            "has_committee_roles": True # don't hide in relevance list
        })
    for csp in bill.cosponsor_records:
        cosponsors.append({
            "person": csp.person,
            "name": csp.person_name, # !
            "party": csp.role.party if csp.role else "Unknown",
            "joined_withdrawn": csp.joined_date_string,
            "sort_cosponsor_type": 1 if not csp.withdrawn else 2,
            "sort_cospsonsor_date": (csp.joined, csp.withdrawn),
        })

    # Make a mapping from person ID to record.
    cosponsor_map = { cm["person"].id: cm for cm in cosponsors }

    from committee.models import CommitteeMember, CommitteeMemberRole, MEMBER_ROLE_WEIGHTS

    # Add a place for committee info.
    for csp in cosponsors:
        csp["committee_roles"] = []
        csp["committee_role_sort"] = [0 for _ in MEMBER_ROLE_WEIGHTS]

    # Annotate with cosponsors that are on relevant committees.
    # Count up the number of times the person has a particular role
    # on any committee (i.e. number of chair positions).
    for cm in CommitteeMember.objects.filter(
        person__in={ c["person"] for c in cosponsors },
        committee__in=bill.committees.all())\
        .select_related("committee", "committee__committee"):
        csp = cosponsor_map[cm.person_id]
        csp["committee_roles"].append(cm)
        csp["committee_roles"].sort(key = lambda cm : (cm.committee.is_subcommittee, -MEMBER_ROLE_WEIGHTS[cm.role] ))
        csp["committee_role_sort"][max(MEMBER_ROLE_WEIGHTS.values()) - MEMBER_ROLE_WEIGHTS[cm.role]] -= 1 # ascending order goes most important to least important
        csp["has_committee_roles"] = True

        # If the parent committee membership role type is just Member,
        # remove it - it's redundant with subcommittee info. But we
        # keep the sort information of the parent committee: i.e.,
        # one subcommittee membership counts as two memberships (once for
        # the parent committee and once for the subcomittee) so that
        # subcommittee membership ranks higher in the sort order than
        # only main-committee membership, since the subcommittee is
        # more specific to the bill.
        if cm.committee.is_subcommittee is not None:
            for cm2 in csp["committee_roles"]:
                if cm2.committee == cm.committee.committee and cm2.role == CommitteeMemberRole.member:
                    csp["committee_roles"].remove(cm2)
                    break

    # Pre-compute the three sort orders that the UI will offer.
    # Assign a row index to each cosponsor for each sort order.

    for i, c in enumerate(sorted(cosponsors, key = lambda c : (
        c["name"],
        c["sort_cosponsor_type"],
    ))):
        c["sort_name"] = i

    for i, c in enumerate(sorted(cosponsors, key = lambda c : (
        c["sort_cosponsor_type"], # sponsor, cosponsors, withdrawn cosponsors
        c["committee_role_sort"], # more important committee roles first
        "\n".join(cm.committee.sortname() for cm in c["committee_roles"]), # keep same committees together
        c["sort_cospsonsor_date"],
        c["name"],
    ))):
        c["sort_relevance"] = i

    for i, c in enumerate(sorted(cosponsors, key = lambda c : (
        c["sort_cosponsor_type"], # sponsor, cosponsors, withdrawn cosponsors
        c["sort_cospsonsor_date"], # join date, then withdrawn date
        c["name"],
    ))):
        c["sort_date"] = i

    # But default to the "relevance" sort.
    cosponsors.sort(key = lambda c : c["sort_relevance"])

    return cosponsors

@user_view_for(bill_full_details)
def bill_full_details_user_view(request, congress, type_slug, number):
    bill = load_bill_from_url(congress, type_slug, number)
    ret = { }
    ret["reactions"] = get_user_bill_reactions(request, bill)
    ret["position"] = get_user_bill_position_info(request, bill)
    return ret

@anonymous_view
@render_to("bill/bill_widget.html")
def bill_widget(request, congress, type_slug, number):
    bill = load_bill_from_url(congress, type_slug, number)

    from person.name import get_person_name
    if bill.sponsor: bill.sponsor.role = bill.sponsor_role # for rending name
    sponsor_name = None if not bill.sponsor else \
        get_person_name(bill.sponsor, firstname_position='before', show_suffix=True)

    return {
        "SITE_ROOT_URL": settings.SITE_ROOT_URL,
        "bill": bill,
        "congressdates": get_congress_dates(bill.congress),
        "subtitle": get_secondary_bill_title(bill, bill.titles),
        "sponsor_name": sponsor_name,
        "current": bill.congress == CURRENT_CONGRESS,
        "dead": bill.congress != CURRENT_CONGRESS and bill.current_status not in BillStatus.final_status_obvious,
        "text": bill.get_text_info(),
    }

@anonymous_view
def bill_widget_loader(request, congress, type_slug, number):
    bill = load_bill_from_url(congress, type_slug, number)

    # @render_to() doesn't support additional parameters, so we have to render manually.
    from django.shortcuts import render
    return render(request, "bill/bill_widget.js", { "bill": bill, "SITE_ROOT_URL": settings.SITE_ROOT_URL }, content_type="text/javascript" )

@anonymous_view
@render_to("bill/bill_widget_info.html")
def bill_widget_info(request, congress, type_slug, number):
    bill = load_bill_from_url(congress, type_slug, number)
    return {
        "bill": bill,
        "SITE_ROOT_URL": settings.SITE_ROOT_URL,
    }


@anonymous_view
@render_to('bill/bill_text.html')
def bill_text(request, congress, type_slug, number, version=None):
    if version == "":
        version = None

    try:
        bill_type = BillType.by_slug(type_slug)
    except BillType.NotFound:
        raise Http404("Invalid bill type: " + type_slug)
    bill = get_object_or_404(Bill, congress=congress, bill_type=bill_type, number=number)

    from .billtext import load_bill_text, get_bill_text_versions
    try:
        textdata = load_bill_text(bill, version)
    except IOError:
        textdata = None

    # Get a list of the alternate versions of this bill.
    alternates = None
    is_latest = True
    if textdata:
        alternates = []
        for v in get_bill_text_versions(bill):
            try:
                alternates.append(load_bill_text(bill, v, mods_only=True))
            except IOError:
                pass
        alternates.sort(key = lambda mods : mods["docdate"])
        if len(alternates) > 0:
            is_latest = False
            if textdata["doc_version"] == alternates[-1]["doc_version"]:
                is_latest = True

    # Get a list of related bills.
    from .billtext import get_current_version
    related_bills = []
    for rb in list(bill.find_reintroductions()) + [r.related_bill for r in bill.get_related_bills()]:
        try:
            rbv = get_current_version(rb)
            if not (rb, rbv) in related_bills: related_bills.append((rb, rbv))
        except IOError:
            pass # text not available
    for btc in BillTextComparison.objects.filter(bill1=bill).exclude(bill2=bill):
        if not (btc.bill2, btc.ver2) in related_bills: related_bills.append((btc.bill2, btc.ver2))
    for btc in BillTextComparison.objects.filter(bill2=bill).exclude(bill1=bill):
        if not (btc.bill1, btc.ver1) in related_bills: related_bills.append((btc.bill1, btc.ver1))

    return {
        "bill_subpage": "Text",
        'bill': bill,
        "congressdates": get_congress_dates(bill.congress),
        "textdata": textdata,
        "version": version,
        "is_latest": is_latest,
        "alternates": alternates,
        "related_bills": related_bills,
        "days_old": (datetime.datetime.now().date() - bill.current_status_date).days,
        "is_on_bill_text_page": True, # for the header tabs
    }

@user_view_for(bill_text)
def bill_text_user_view(request, congress, type_slug, number, version=None):
    bill = load_bill_from_url(congress, type_slug, number)
    ret = { }
    ret["reactions"] = get_user_bill_reactions(request, bill)
    ret["position"] = get_user_bill_position_info(request, bill)
    return ret

@anonymous_view
@json_response
def bill_text_ajax(request):
    # Load a bill text comparison.

    for p in ("left_bill", "left_version", "right_bill", "right_version", "mode"):
        if not p in request.GET:
            raise Http404()

    from .billtext import load_bill_text, get_current_version

    # Load the bills and get the versions to compare.
    try:
        left_bill = Bill.objects.get(id=request.GET['left_bill'])
        left_version = request.GET['left_version']

        right_bill = Bill.objects.get(id=request.GET['right_bill'])
        right_version = request.GET['right_version']

        if left_version == "": left_version = get_current_version(left_bill)
        if right_version == "": right_version = get_current_version(right_bill)

        left_metadata = load_bill_text(left_bill, left_version, mods_only=True)
        right_metadata = load_bill_text(right_bill, right_version, mods_only=True)
    except Exception as e:
        return { "error": str(e) }


    # Swap the order so the left is the earlier document.
    if left_metadata["docdate"] > right_metadata["docdate"]:
        left_bill, right_bill = right_bill, left_bill
        left_version, right_version = right_version, left_version
        left_metadata, right_metadata = right_metadata, left_metadata

    # If PDFs are available for both, use the Draftable API.

    if "pdf_file" in left_metadata and "pdf_file" in right_metadata \
        and hasattr(settings, 'DRAFTABLE_ACCOUNT_ID'):
        import draftable
        draftable_client = draftable.Client(settings.DRAFTABLE_ACCOUNT_ID, settings.DRAFTABLE_AUTH_TOKEN)
        comparison_id = "billtext_c1_{}_{}_{}_{}_{}_{}".format(
            left_bill.congressproject_id, left_version, "pdf",
            right_bill.congressproject_id, right_version, "pdf",
        )

        # See if we've done this one already.
        comparison = None
        try:
            comparison = draftable_client.comparisons.get(comparison_id)
        except:
            pass

        if not comparison:
            def load_side(bill, metadata):
                from time import strftime
                return draftable.make_side(
                    metadata['pdf_file'],
                    file_type="pdf",
                    display_name="{}: {} ({})".format(
                        bill.display_number_with_congress_number,
                        metadata["doc_version_name"],
                        metadata["docdate"].strftime("%x")))
            comparison = draftable_client.comparisons.create(
                identifier=comparison_id,
                left=load_side(left_bill, left_metadata),
                right=load_side(right_bill, right_metadata),
                public=True,
            )

        return { "draftable_widget_url": draftable_client.comparisons.public_viewer_url(identifier=comparison_id, wait=True) }

    # Do our own diff and return the diff as XML content.

    try:
        return make_bill_text_comparison(left_bill, left_version, right_bill, right_version)
    except IOError as e:
        return { "error": str(e) }

def make_bill_text_comparison(left_bill, left_version, right_bill, right_version):
    timelimit = 10
    use_cache = True
    force_update=False

    from xml_diff import compare
    import lxml

    if use_cache:
        # Load from cache.
        try:
            btc = BillTextComparison.objects.get(
                bill1 = left_bill,
                ver1 = left_version,
                bill2 = right_bill,
                ver2 = right_version)
            btc.decompress()
            return btc.data
        except BillTextComparison.DoesNotExist:
            pass

        # Load from cache - Try with the bills swapped.
        try:
            btc2 = BillTextComparison.objects.get(
                bill2 = left_bill,
                ver2 = left_version,
                bill1 = right_bill,
                ver1 = right_version)
            btc2.decompress()
            data = btc2.data
            # un-swap
            return {
                "left_meta": data["right_meta"],
                "right_meta": data["left_meta"],
                "left_text": data["right_text"],
                "right_text": data["left_text"],
            }
        except BillTextComparison.DoesNotExist:
            pass

    # Load bill text metadata.
    left = load_bill_text(left_bill, left_version, mods_only=True)
    right = load_bill_text(right_bill, right_version, mods_only=True)

    # Load XML DOMs for each document and perform the comparison.
    def load_bill_text_xml(docinfo):
        # If XML text is available, use it, but pre-render it
        # into HTML. Otherwise use the legacy HTML that we
        # scraped from THOMAS.
        if "xml_file" in docinfo:
            import congressxml
            return congressxml.convert_xml(docinfo["xml_file"])
        elif "html_file" in docinfo:
            return lxml.etree.parse(docinfo["html_file"])
        else:
            raise IOError("Bill text is not available for one of the bills.")
    doc1 = load_bill_text_xml(left)
    doc2 = load_bill_text_xml(right)
    def make_tag_func(ins_del):
        import lxml.etree
        elem = lxml.etree.Element("comparison-change")
        return elem
    #def differ(text1, text2):
    #    import diff_match_patch
    #    for x in diff_match_patch.diff(text1, text2, timelimit=timelimit):
    #        yield x
    compare(doc1.getroot(), doc2.getroot(), make_tag_func=make_tag_func)#, differ=differ)

    # Prepare JSON response data.
        # dates aren't JSON serializable
    left["docdate"] = left["docdate"].strftime("%x")
    right["docdate"] = right["docdate"].strftime("%x")
    ret = {
        "left_meta": left,
        "right_meta": right,
        "left_text": lxml.etree.tostring(doc1, encoding=str),
        "right_text": lxml.etree.tostring(doc2, encoding=str),
    }

    if use_cache or force_update:
        # For force_update, or race conditions, delete any existing record.
        fltr = { "bill1": left_bill,
            "ver1": left_version,
            "bill2": right_bill,
            "ver2": right_version }
        BillTextComparison.objects.filter(**fltr).delete()

        # Cache in database so we don't have to re-do the comparison
        # computation again.
        btc = BillTextComparison(
            data = dict(ret), # clone before compress()
            **fltr)
        btc.compress()
        btc.save()

    # Return JSON comparison data.
    return ret

def bill_list(request):
    if request.POST.get("allow_redirect", "") == "true":
        bill = parse_bill_citation(request.POST.get("text", ""), congress=request.POST.get("congress", ""))
        if bill:
            @json_response
            def get_redirect_response():
                return { "redirect": bill.get_absolute_url() }
            return get_redirect_response()

    ix1 = None
    ix2 = None
    if "subject" in request.GET:
        try:
            ix = BillTerm.objects.get(id=request.GET["subject"])
        except ValueError:
            raise Http404()
        if ix.parents.all().count() == 0:
            ix1 = ix
        else:
            ix1 = ix.parents.all()[0]
            ix2 = ix
    return show_bill_browse("bill/bill_list.html", request, ix1, ix2, { })

def show_bill_browse(template, request, ix1, ix2, context):
    if "sort" in request.GET:
        # pass through
        default_sort = request.GET["sort"]
    elif "text" in request.GET:
        # when the user is doing a text search, sort by standard Solr relevance scoring, which includes boosting the bill title
        default_sort = None
    elif "sponsor" in request.GET:
        # when searching by sponsor, the default order is to show bills in reverse chronological order
        default_sort = "-introduced_date"
    else:
        # otherwise in faceted searching, order by -proscore which puts more important bills up top
	    default_sort = "-proscore"

    return bill_search_manager().view(request, template,
        defaults={
            "congress": request.GET["congress"] if "congress" in request.GET else (CURRENT_CONGRESS if "sponsor" not in request.GET else None), # was Person.objects.get(id=request.GET["sponsor"]).most_recent_role_congress(), but we can just display the whole history which is better at the beginning of a Congress when there are no bills
            "sponsor": request.GET.get("sponsor", None),
            "terms": ix1.id if ix1 else None,
            "terms2": ix2.id if ix2 else None,
            "text": request.GET.get("text", None),
            "current_status": request.GET.get("status").split(",") if "status" in request.GET else None,
            "sort": default_sort,
            "usc_cite": request.GET.get("usc_cite"),
        },
        noun = ("bill", "bills"),
        context = context,
        )

def query_popvox(method, args):
    if isinstance(method, (list, tuple)):
        method = "/".join(method)

    _args = { }
    if args != None: _args.update(args)
    _args["api_key"] = settings.POPVOX_API_KEY

    url = "https://www.popvox.com/api/" + method + "?" + urllib.parse.urlencode(_args).encode("utf8")

    req = urllib.request.Request(url)
    resp = urllib.request.urlopen(req)
    if resp.getcode() != 200:
        raise Exception("Failed to load page: " + url)
    ret = resp.read()
    encoding = resp.info().getparam("charset")
    ret = ret.decode(encoding)
    return json.loads(ret)

subject_choices_data = None
def subject_choices():
    global subject_choices_data
    if subject_choices_data == None:
        subject_choices_data = { }
        for t in BillTerm.objects.filter(term_type=TermType.new).exclude(parents__id__gt=0).prefetch_related("subterms"):
            x = []
            subject_choices_data[t] = x
            for tt in t.subterms.all():
                x.append(tt)
        subject_choices_data = sorted(subject_choices_data.items(), key = lambda x : x[0].name)
    return subject_choices_data

# used by bills_overview and bill_statistics
bill_status_groups = [
    ("Enacted Laws",
        "enacted bills and joint resolutions", " so far in this session of Congress", " (both bills and joint resolutions can be enacted as law)",
        BillStatus.final_status_enacted_bill), # 2
    ("Passed Resolutions",
        "passed resolutions", " so far in this session of Congress (for joint and concurrent resolutions, passed both chambers)", " (for joint and concurrent resolutions, this means passed both chambers)",
        BillStatus.final_status_passed_resolution), # 3
    ("Got A Vote",
        "bills and joint/concurrent resolutions", " that had a significant vote in one chamber, making them likely to have further action", " that had a significant vote in one chamber",
        (BillStatus.pass_over_house, BillStatus.pass_over_senate, BillStatus.pass_back_senate, BillStatus.pass_back_house, BillStatus.conference_passed_house, BillStatus.conference_passed_senate, BillStatus.passed_bill)), # 7
    ("Failed Legislation",
        "bills and resolutions", " that failed a vote on passage and are now dead or failed a significant vote such as cloture, passage under suspension, or resolving differences", " that failed a vote on passage or failed a significant vote such as cloture, passage under suspension, or resolving differences",
        (BillStatus.fail_originating_house, BillStatus.fail_originating_senate, BillStatus.fail_second_house, BillStatus.fail_second_senate, BillStatus.prov_kill_suspensionfailed, BillStatus.prov_kill_cloturefailed, BillStatus.prov_kill_pingpongfail)), # 7
    ("Vetoed Bills (w/o Override)",
        "bills", " that were vetoed and the veto was not overridden by Congress", " that were vetoed and the veto was not overridden by Congress",
        (BillStatus.prov_kill_veto, BillStatus.override_pass_over_house, BillStatus.override_pass_over_senate, BillStatus.vetoed_pocket, BillStatus.vetoed_override_fail_originating_house, BillStatus.vetoed_override_fail_originating_senate, BillStatus.vetoed_override_fail_second_house, BillStatus.vetoed_override_fail_second_senate)), # 8
    ("Other Legislation",
        "bills and resolutions", " that have been introduced or reported by committee and await further action", " that were introduced, referred to committee, or reported by committee but had no further action",
        (BillStatus.introduced, BillStatus.reported)), # 3
]

def load_bill_status_qs(statuses, congress=CURRENT_CONGRESS):
    return Bill.objects.filter(congress=congress, current_status__in=statuses)

@anonymous_view
@render_to('bill/bills_overview.html')
def bills_overview(request):
    def build_info():
        # feeds about all legislation that we offer the user to subscribe to
        feeds = [f for f in Feed.get_simple_feeds() if f.category == "federal-bills"]

        # info about bills by status
        groups = [
            (   g[0], # title
                g[1], # text 1
                g[2], # text 2
                "/congress/bills/browse?status=" + ",".join(str(s) for s in g[4]) + "&sort=-current_status_date", # link
               load_bill_status_qs(g[4]).count(), # count in category
               load_bill_status_qs(g[4]).order_by('-current_status_date')[0:6], # top 6 in this category
                )
            for g in bill_status_groups ]

        # legislation coming up
        dhg_bills = Bill.objects.filter(congress=CURRENT_CONGRESS, docs_house_gov_postdate__gt=datetime.datetime.now() - datetime.timedelta(days=10)).filter(docs_house_gov_postdate__gt=F('current_status_date'))
        sfs_bills = Bill.objects.filter(congress=CURRENT_CONGRESS, senate_floor_schedule_postdate__gt=datetime.datetime.now() - datetime.timedelta(days=5)).filter(senate_floor_schedule_postdate__gt=F('current_status_date'))
        coming_up = list((dhg_bills | sfs_bills).order_by('scheduled_consideration_date'))

        # top tracked bills
        top_bills = Feed.objects\
            .filter(feedname__startswith='bill:')\
            .filter(feedname__regex='^bill:[hs][jcr]?%d-' % CURRENT_CONGRESS)
        top_bills = top_bills\
            .annotate(count=Count('tracked_in_lists'))\
            .order_by('-count')\
            .values('feedname', 'count')\
            [0:25]
        top_bills = [(Bill.from_feed(Feed.from_name(bf["feedname"])), bf["count"]) for bf in top_bills]

        # trending bills
        trf = Feed.get_trending_feeds()
        trf = [Feed.objects.get(id=f) for f in trf]
        trending_bill_feeds = [f for f in trf if f.feedname.startswith("bill:")]

        return {
            "feeds": feeds,

            "total": Bill.objects.filter(congress=CURRENT_CONGRESS).count(),
            "current_congress": CURRENT_CONGRESS,
            "current_congress_dates": get_congress_dates(CURRENT_CONGRESS),

            "groups": groups,
            "coming_up": coming_up,
            "top_tracked_bills": top_bills,
            "trending_bill_feeds": trending_bill_feeds,

            "subjects": subject_choices(),
            "BILL_STATUS_INTRO": (BillStatus.introduced, BillStatus.reported),
        }

    ret = cache.get("bills_overview_info")
    if not ret:
        ret = build_info()
        cache.set("bills_overview_info", ret, 60*60)

    return ret

@anonymous_view
@render_to('bill/bill_statistics.html')
def bill_statistics(request):
    # Get the count of bills by status and by Congress.
    counts_by_congress = []
    for c in range(93, CURRENT_CONGRESS+1):
        total = Bill.objects.filter(congress=c).count()
        if total == 0: continue # during transitions between Congresses
        counts_by_congress.append({
            "congress": c,
            "dates": get_congress_dates(c),
            "counts": [ ],
            "total": total,
        })
        for g in bill_status_groups:
            t = load_bill_status_qs(g[4], congress=c).count()
            counts_by_congress[-1]["counts"].append(
                { "count": t,
                  "percent": "%0.0f" % float(100.0*t/total),
                  "link": "/congress/bills/browse?congress=%s&status=%s" % (c, ",".join(str(s) for s in g[4])),
                  } )
    counts_by_congress.reverse()

    # When does activity occur within the session cycle?
    if settings.DATABASES['default']['ENGINE'] != 'django.db.backends.sqlite3':
        from django.db import connection
        def pull_time_stat(field, where, cursor):
            cursor.execute("SELECT YEAR(%s) - congress*2 - 1787, MONTH(%s), COUNT(*) FROM bill_bill WHERE congress >= 93 AND %s GROUP BY YEAR(%s) - congress*2, MONTH(%s)" % (field, field, where, field, field))
            activity = [{ "x": r[0]*12 + (r[1]-1), "count": r[2], "year": r[0] } for r in cursor.fetchall()]
            total = sum(m["count"] for m in activity)
            for i, m in enumerate(activity): m["cumulative_count"] = m["count"]/float(total) + (0.0 if i==0 else activity[i-1]["cumulative_count"])
            for m in activity: m["count"] = round(m["count"] / float(total) * 100.0, 1)
            for m in activity: m["cumulative_count"] = round(m["cumulative_count"] * 100.0)
            return activity
        with connection.cursor() as cursor:
            activity_introduced_by_month = pull_time_stat('introduced_date', "1", cursor)
            activity_enacted_by_month = pull_time_stat('current_status_date', "current_status IN (%d,%d,%d)" % (int(BillStatus.enacted_signed), int(BillStatus.enacted_veto_override), int(BillStatus.enacted_tendayrule)), cursor)
    else:
        activity_introduced_by_month = []
        activity_enacted_by_month = []

    return {
        "groups2": bill_status_groups,
        "counts_by_congress": counts_by_congress,
        "activity": (("Bills Introduced", activity_introduced_by_month),
         ("Laws Enacted", activity_enacted_by_month) )
    }

@anonymous_view
def subject(request, sluggedname, termid):
    ix = get_object_or_404(BillTerm, id=termid)
    if ix.parents.all().count() == 0:
        ix1 = ix
        ix2 = None
    else:
        ix1 = ix.parents.all()[0]
        ix2 = ix
    return show_bill_browse("bill/subject.html", request, ix1, ix2, { "term": ix, "feed": ix.get_feed() })

@user_view_for(subject)
def subject_user_view(request, sluggedname, termid):
    ix = get_object_or_404(BillTerm, id=termid)
    ret = { }
    from person.views import render_subscribe_inline
    ret.update(render_subscribe_inline(request, ix.get_feed()))
    return ret

import django.contrib.sitemaps
class sitemap_current(django.contrib.sitemaps.Sitemap):
    changefreq = "weekly"
    priority = 1.0
    def items(self):
        return Bill.objects.filter(congress=CURRENT_CONGRESS).only("congress", "bill_type", "number")
class sitemap_archive(django.contrib.sitemaps.Sitemap):
    index_levels = ['congress']
    changefreq = "yearly"
    priority = 0.25
    def items(self):
        return Bill.objects.filter(congress__lt=CURRENT_CONGRESS).only("congress", "bill_type", "number")

@render_to('bill/bill_advocacy_tips.html')
def bill_advocacy_tips(request, congress, type_slug, number):
    try:
        bill_type = BillType.by_slug(type_slug)
    except BillType.NotFound:
        raise Http404("Invalid bill type: " + type_slug)
    bill = get_object_or_404(Bill, congress=congress, bill_type=bill_type, number=number)
    return { "bill": bill }

@json_response
@login_required
def join_community(request):
    from website.models import CommunityInterest
    from bill.models import Bill
    methods = request.POST["methods"].strip()
    if methods == "":
        CommunityInterest.objects.filter(user=request.user, bill=request.POST["bill"]).delete()
    else:
        c, isnew = CommunityInterest.objects.get_or_create(user=request.user, bill=Bill.objects.get(id=request.POST["bill"]))
        c.methods = methods
        c.save()
    return { "status": "OK" }

from django.contrib.auth.decorators import permission_required
@permission_required('bill.change_billsummary')
def go_to_summary_admin(request):
    summary, is_new = BillSummary.objects.get_or_create(bill=get_object_or_404(Bill, id=request.GET["bill"]))
    return HttpResponseRedirect("/admin/bill/billsummary/%d" % summary.id)

@anonymous_view
@render_to('bill/uscode_index.html')
def uscodeindex(request, secid):
    from bill.models import USCSection
    if not secid:
        parent = None
    elif re.match(r"\d+$", secid):
        parent = get_object_or_404(USCSection, id=secid)
    else:
        parent = get_object_or_404(USCSection, citation="usc/" + secid)

    children = USCSection.objects.filter(parent_section=parent).order_by('ordering')

    from haystack.query import SearchQuerySet
    qs = SearchQuerySet().using("bill").filter(indexed_model_name__in=["Bill"])
    qs_current = qs.filter(congress=CURRENT_CONGRESS)

    # How many bills cite this section?
    num_bills = qs_current.filter(usc_citations_uptree=parent.id).count() if parent else qs_current.count()

    # Mark the children if we should allow the user to navigate there.
    # Only let them go to parts of the table of contents where there
    # are lots of bills to potentially track, at least historically.
    has_child_navigation = False
    for c in children:
        c.num_bills = qs.filter(usc_citations_uptree=c.id).count()
        c.allow_navigation = c.num_bills > 5
        has_child_navigation |= c.allow_navigation
    
    return {
        "parent": parent,
        "children": children,
        "has_child_navigation": has_child_navigation,
        "num_bills_here": num_bills,
        "bills_here": (qs_current.filter(usc_citations_uptree=parent.id) if parent else qs) if num_bills < 100 else None,
        "base_template": 'master_c.html' if parent else "master_b.html",
        "feed": (Feed.objects.get_or_create(feedname="usc:" + str(parent.id))[0]) if parent else None,
    }

@anonymous_view
def bill_text_image(request, congress, type_slug, number, image_type):
    # Get bill.
    bill = load_bill_from_url(congress, type_slug, number)
    from .billtext import load_bill_text

    # What size image are we asked to generate?
    try:
        width = int(request.GET["width"])
    except:
        width = 0 # don't resize

    # We're going to display this next to photos of members of congress,
    # so use that aspect ratio by default.
    try:
        aspect = float(request.GET["aspect"])
    except:
        aspect = 240.0/200.0
    if image_type == "card": aspect = .5 # height/width

    # Rasterizes a page of a PDF to a greyscale PIL.Image.
    # Crop out the GPO seal & the vertical margins.
    def pdftopng(pdffile, pagenumber, width=900):
        from PIL import Image
        import subprocess, io
        pngbytes = subprocess.check_output(["/usr/bin/pdftoppm", "-f", str(pagenumber), "-l", str(pagenumber), "-scale-to", str(width), "-png", pdffile])
        im = Image.open(io.BytesIO(pngbytes))
        im = im.convert("L")

        # crop out the GPO seal:
        im = im.crop((0, int((.06 if pagenumber==1 else 0) * im.size[0]), im.size[0], im.size[1]))

        # zealous-crop the vertical margins, but at least leaving a little
        # at the bottom so that when we paste the two pages of the two images
        # together they don't get totally scruntched, and put in some padding
        # at the top.
        # (.getbbox() crops out zeroes, so we'll invert the image to make it work with white)
        from PIL import ImageOps
        bbox = ImageOps.invert(im).getbbox()
        vpad = int(.02*im.size[1])
        im = im.crop( (0, max(0, bbox[1]-vpad), im.size[0], min(im.size[1], bbox[3]+vpad) ) )

        return im

    # Find the PDF file and rasterize the first two pages.

    try:
        metadata = load_bill_text(bill, None, mods_only=True)
    except IOError:
        # if bill text metadata isn't available, we won't show the bill text as a part of the thumbnail
        metadata = None

    cache_fn = None

    from PIL import Image

    if not metadata:
        # Start with a blank page.
        w = max(width, 100)
        pg1 = Image.new("RGB", (w, int(aspect*w)), color=(255,255,255))
        pg2 = pg1
    elif metadata.get("pdf_file"):
        # Check if we have a cached file. We want to cache longer than our HTTP cache
        # because these thumbnails basically never change and calling pdftoppm is expensive.
        import os.path
        cache_fn = metadata["pdf_file"].replace(".pdf", "-" + image_type + "_" + str(width) + "_" + str(round(aspect,3)) + ".png")
        if os.path.exists(cache_fn):
            with open(cache_fn, "rb") as f:
                return HttpResponse(f.read(), content_type="image/png")

        # Use the PDF files on disk.
        pg1 = pdftopng(metadata.get("pdf_file"), 1)
        try:
            pg2 = pdftopng(metadata.get("pdf_file"), 2)
        except:
            pg2 = pg1.crop((0, 0, pg1.size[0], 0)) # may only be one page!
    elif settings.DEBUG:
        # When debugging in a local environment we may not have bill text available
        # so download the PDF from GPO.
        import os, tempfile, subprocess
        try:
            (fd1, fn1) = tempfile.mkstemp(suffix=".pdf")
            os.close(fd1)
            subprocess.check_call(["/usr/bin/wget", "-O", fn1, "-q", metadata["gpo_pdf_url"]])
            pg1 = pdftopng(fn1, 1)
            pg2 = pdftopng(fn1, 2)
        finally:
            os.unlink(fn1)
    else:
        # No PDF is available.
        raise Http404()

    # Since some bills have big white space at the top of the first page,
    # we'll combine the first two pages and then shift the window down
    # until the real start of the bill.
    
    img = Image.new(pg1.mode, (pg1.size[0], int(pg1.size[1]+pg2.size[1])))
    img.paste(pg1, (0,0))
    img.paste(pg2, (0,pg1.size[1]))

    # Zealous crop the (horizontal) margins. We do this only after the two
    # pages have been combined so that we don't mess up their alignment.
    # Add some padding.
    from PIL import ImageOps
    hpad = int(.02*img.size[0])
    bbox = ImageOps.invert(img).getbbox()
    if bbox: # if image is empty, bbox is None
        img = img.crop( (max(0, bbox[0]-hpad), 0, min(img.size[0], bbox[2]+hpad), img.size[1]) )

    # Now take a window from the top matching a particular aspect ratio.
    img = img.crop((0,0, img.size[0], int(aspect*img.size[0])))

    # Resize to requested width.
    if width:
        img.thumbnail((width, int(aspect*width)), Image.ANTIALIAS)

    # Add symbology.
    if image_type in ("thumbnail", "card"):
        img = img.convert("RGBA")

        banner_color = None
        party_colors = { "Republican": (230, 14, 19, 150), "Democrat": (0, 65, 161, 150) }
        if bill.sponsor_role: banner_color = party_colors.get(bill.sponsor_role.party)
        if banner_color:
            from PIL import ImageDraw
            im = Image.new("RGBA", img.size, (0,0,0,0))
            draw = ImageDraw.Draw(im)
            draw.rectangle(((0, int(.85*im.size[1])), im.size), outline=None, fill=banner_color)
            del draw
            img = Image.alpha_composite(img, im)

        if bill.sponsor and bill.sponsor.has_photo():
            im = Image.open("." + bill.sponsor.get_photo_url(200))
            im.thumbnail( [int(x/2.5) for x in img.size] )
            img.paste(im, (int(.05*img.size[1]), int(.95*img.size[1])-im.size[1]))

        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        draw.rectangle(((0, 0), (img.size[0]-1, img.size[1]-1)), outline=(100,100,100,255), fill=None)
        del draw

    # Serialize.
    import io
    imgbytesbuf = io.BytesIO()
    img.save(imgbytesbuf, "PNG")
    imgbytes = imgbytesbuf.getvalue()
    imgbytesbuf.close()

    # Save to cache.
    if cache_fn:
        with open(cache_fn, "wb") as f:
            f.write(imgbytes)

    # Return.
    return HttpResponse(imgbytes, content_type="image/png")

@anonymous_view
def bill_get_json(request, congress, type_slug, number):
    bill = load_bill_from_url(congress, type_slug, number)
    return HttpResponseRedirect("/api/v2/bill/%d" % bill.id)

@anonymous_view
@render_to('bill/bill_contact_congress.html')
def bill_contact_congress(request, congress, type_slug, number):
    bill = load_bill_from_url(congress, type_slug, number)
    return {
        "bill": bill,
        "MAPBOX_ACCESS_TOKEN": settings.MAPBOX_ACCESS_TOKEN,
        "MAPBOX_MAP_STYLE": settings.MAPBOX_MAP_STYLE,
        "MAPBOX_MAP_ID": settings.MAPBOX_MAP_ID,
    }


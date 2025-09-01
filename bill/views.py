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
from person.models import Person, PersonRole, RoleType
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
    text_info = bill.get_text_info()

    # load president who made Statement of Administration policy
    if bill.statement_admin_policy:
        from parser.processor import Processor
        bill.statement_admin_policy["president"] = Person.objects.get(id=bill.statement_admin_policy["president"])
        bill.statement_admin_policy["date_issued"] = Processor.parse_datetime(bill.statement_admin_policy["date_issued"])

    # context
    return {
        'bill': bill,
        "congressdates": get_congress_dates(bill.congress),
        "subtitle": get_secondary_bill_title(bill, bill.titles),
        "current": bill.congress == CURRENT_CONGRESS,
        "dead": bill.congress != CURRENT_CONGRESS and bill.current_status not in BillStatus.final_status_obvious,
        "feed": bill.get_feed(),
        "prognosis": bill.get_prognosis(),
        "text_info": text_info,
        "text_incorporation": fixup_text_incorporation(bill.text_incorporation),
        "show_media_bar": not bill.original_intent_replaced and bill.sponsor and bill.sponsor.has_photo() and text_info and text_info.get("has_thumbnail"),
    }

@anonymous_view
@render_to('bill/bill_key_questions.html')
def bill_key_questions(request, congress, type_slug, number):
    # load bill and text
    bill = load_bill_from_url(congress, type_slug, number)
    text_info = bill.get_text_info(with_citations=True)

    # context
    return {
        'bill': bill,
        "congressdates": get_congress_dates(bill.congress),
        "dead": bill.congress != CURRENT_CONGRESS and bill.current_status not in BillStatus.final_status_obvious,
        "text_info": text_info,
        "text_incorporation": fixup_text_incorporation(bill.text_incorporation),
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

    from website.views import community_forum_userdata
    ret["community_forum"] = community_forum_userdata(request, bill.get_feed().feedname)

    return ret

def get_user_bill_reactions(request, bill):
    from website.models import Reaction

    # get aggregate counts
    reaction_subject = "bill:" + bill.congressproject_id
    emoji_counts = { }
    for r in Reaction.objects.filter(subject=reaction_subject).values("reaction").annotate(count=Count('id')):
        v = r["reaction"]
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
    }


@anonymous_view
@render_to("bill/bill_cosponsors.html")
def bill_cosponsors(request, congress, type_slug, number):
    bill = load_bill_from_url(congress, type_slug, number)
    return {
        "bill_subpage": "Cosponsors",
        "bill": bill,
        "text_info": bill.get_text_info(with_citations=True), # for the header tabs
        "cosponsors": get_cosponsors_table(bill, mode="cosponsors"),
        "possible_cosponsors": get_cosponsors_table(bill, mode="others"),
    }

def get_cosponsors_table(bill, mode=None):
    from committee.models import CommitteeMember, CommitteeMemberRole, MEMBER_ROLE_WEIGHTS

    def make_name(person, role):
        # don't need title because it's implicit from the bill type
        from person.name import get_person_name
        person.role = role
        return get_person_name(person, firstname_position="after", show_title=False)

    cosponsor_records = {
        csp.person: csp
        for csp in bill.cosponsor_records
    }

    cosponsors = []
    cosponsor_map = { }

    def add_cosponsor(person, role):
        if person.id in cosponsor_map: return cosponsor_map[person.id]
        csp = cosponsor_records.get(person)
        rec = {
            "person": person,
            "name": make_name(person, role),
            "party": role.party if role else "Unknown",
            "joined_withdrawn":
                "Primary Sponsor" if person == bill.sponsor
                else csp.joined_date_string if csp is not None
                else None,
            "sort_cosponsor_type":
                0 if person == bill.sponsor # sponsor
                else 1 if csp is not None and not csp.withdrawn # cosponsor
                else 2 if csp is not None # withdrawn
                else 3, # not ever a sponsor/cosponsor
            "sort_cospsonsor_date": # must match sort_cosponsor_type because the '...type' buckets first and date comparisons are only made within those groups
                None if person == bill.sponsor
                else csp.joined if csp is not None and not csp.withdrawn
                else csp.withdrawn if csp is not None
                else None,
            "has_committee_roles": True if person == bill.sponsor else None # don't hide sponsor in relevance list
        }
        cosponsors.append(rec)
        cosponsor_map[rec["person"].id] = rec
        return rec

    if mode == "cosponsors":
        # Get all sponsor/cosponsors.
        if bill.sponsor is not None: # historical bills may be missing this
            add_cosponsor(bill.sponsor, bill.sponsor_role)
        for csp in cosponsor_records.values():
            add_cosponsor(csp.person, csp.role)
    elif mode == "others":
        # Collect legislators who are relevant to this bill, without
        # regard to whether they are a cosponsor of this bill, but
        # annotate if they are.
        for mbr in { r.person for r in CommitteeMember.objects.filter(committee__in=bill.committees.all()) }: # uniqueify
            add_cosponsor(mbr, mbr.current_role)
        for rb in bill.find_reintroductions():
          for csp in rb.cosponsor_records:
              if csp.person.current_role: # exclude legislators no longer serving
                  add_cosponsor(csp.person, csp.person.current_role).setdefault("other_bills", []).append(rb)

        # If the bill has a lot of cosponsors, it's interesting to see who is not a cosponsor
        # among currently serving legislators.
        if len(cosponsor_records) > .75 * (441 if bill.originating_chamber == "House" else 100):
            for r in PersonRole.objects.filter(current=True, role_type=RoleType.representative if bill.originating_chamber == "House" else RoleType.senator):
                  if r.person != bill.sponsor and r.person not in cosponsor_records:
                      add_cosponsor(r.person, r)

    # Add a place for committee info.
    for csp in cosponsors:
        csp["committee_roles"] = []
        csp["committee_role_sort"] = [0 for _ in MEMBER_ROLE_WEIGHTS]

    has_committee_roles = False
    if True:
        # Annotate cosponsors that are on relevant committees.
        # Count up the number of times the person has a particular role
        # on any committee (i.e. number of chair positions). Our committee
        # membership data is current committee assignments which for
        # non-alive bills can't answer the question of what the cosponsors'
        # committee assignments were when the bill was alive. However,
        # as D.S. tells me, current committee assignments are more relevant
        # anyway for advocacy on the same issue as the bill.
        for cm in CommitteeMember.objects.filter(
          person__in={ c["person"] for c in cosponsors },
          committee__in=bill.committees.all())\
          .select_related("committee", "committee__committee"):
            csp = cosponsor_map[cm.person_id]
            csp["committee_roles"].append(cm)
            csp["committee_roles"].sort(key = lambda cm : (cm.committee.is_subcommittee, -MEMBER_ROLE_WEIGHTS[cm.role] ))
            csp["committee_role_sort"][max(MEMBER_ROLE_WEIGHTS.values()) - MEMBER_ROLE_WEIGHTS[cm.role]] -= 1 # ascending order goes most important to least important
            csp["has_committee_roles"] = True
            has_committee_roles = True

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
        c["name"], # we're sorting by name
        c["sort_cosponsor_type"], # and in an unlikely case of a name clash, sort then by sponsor/cosponsor/withdrawn
    ))):
        c["sort_name"] = i

    for i, c in enumerate(sorted(cosponsors, key = lambda c : (
        c["sort_cosponsor_type"] if mode == "cosponsors" else 0, # sponsor, cosponsors, withdrawn cosponsors; don't sort this way for others mode
        c["committee_role_sort"], # more important committee roles first
        "\n".join(cm.committee.sortname() for cm in c["committee_roles"]), # keep same committees together
        c["sort_cospsonsor_date"] if mode == "cosponsors" else 0, # in 'others' mode since we don't bucket by sort_sponsor_type then sort_cospsonsor_date is not comparable
        c["party"] != bill.sponsor_role.party if mode == "others" and bill.sponsor_role else 0, # same party first
        c["name"],
    ))):
        c["sort_relevance"] = i

    for i, c in enumerate(sorted(cosponsors, key = lambda c : (
        c["sort_cosponsor_type"], # sponsor, cosponsors, withdrawn cosponsors
        c["sort_cospsonsor_date"], # join date, then withdrawn date
        c["name"],
    ))):
        c["sort_date"] = i

    # Default to the "relevance" sort --- this matches the
    # initial activate state of the sort links in the HTML.
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
        get_person_name(bill.sponsor, firstname_position='before')

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
    from .billtext import load_bill_text
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
    ("Enacted Legislation (including via incorporation)",
        "enacted bills", "including bills and joint resolutions identical to or incorporated into enacted legislation, based on an automated GovTrack.us data analysis",
        "including bills (and joint resolutions) identical to or incorporated into enacted legislation, based on an approximate, automated GovTrack.us data analysis that varies by Congress",
        "enacted_ex"),
    ("Enacted Legislation",
        "enacted bills", "that were either signed by the president or enacted via a veto override or the 10-day rule (including joint resolutions which can also be enacted as law)", None,
        BillStatus.final_status_enacted_bill), # 2
    ("Passed Resolutions",
        "passed resolutions", "(for joint and concurrent resolutions, we mean passed both chambers)", None,
        BillStatus.final_status_passed_resolution), # 3
    ("Got A Vote",
        "bills and resolutions", "that had a significant vote in one chamber, making them likely to have further action", "that had a significant vote in one chamber but were not enacted (or, for resolutions, passed)",
        (BillStatus.pass_over_house, BillStatus.pass_over_senate, BillStatus.pass_back_senate, BillStatus.pass_back_house, BillStatus.conference_passed_house, BillStatus.conference_passed_senate, BillStatus.passed_bill)), # 7
    ("Failed Legislation",
        "bills and resolutions", "that failed a vote on passage and are dead or failed a significant vote such as cloture, passage under suspension, or resolving differences", None,
        (BillStatus.fail_originating_house, BillStatus.fail_originating_senate, BillStatus.fail_second_house, BillStatus.fail_second_senate, BillStatus.prov_kill_suspensionfailed, BillStatus.prov_kill_cloturefailed, BillStatus.prov_kill_pingpongfail)),
    ("Vetoed Bills (without Override)",
        "vetoed bills", "that was not overridden by Congress", None,
        (BillStatus.prov_kill_veto, BillStatus.override_pass_over_house, BillStatus.override_pass_over_senate, BillStatus.vetoed_pocket, BillStatus.vetoed_override_fail_originating_house, BillStatus.vetoed_override_fail_originating_senate, BillStatus.vetoed_override_fail_second_house, BillStatus.vetoed_override_fail_second_senate)), # 8
    ("Other Legislation",
        "bills and resolutions", "that have been introduced or reported by committee and await further action", "that were introduced or reported by committee but did not have further action",
        (BillStatus.introduced, BillStatus.reported)), # 3
]

def load_bill_status_qs(statuses, congress=CURRENT_CONGRESS):
    if statuses != "enacted_ex":
        return Bill.objects.filter(congress=congress, current_status__in=statuses)
    else:
        from haystack.query import SearchQuerySet
        return SearchQuerySet().using("bill").filter(indexed_model_name__in=["Bill"], enacted_ex=True, congress=congress)

def load_bill_status_search_link(congress, statuses):
    return "/congress/bills/browse?sort=-current_status_date" \
           + ("&congress={}".format(congress) if congress else "") \
           + (("&status=" + ",".join(str(s) for s in statuses)) if statuses != "enacted_ex" \
             else "#enacted_ex=on")

@anonymous_view
@render_to('bill/bills_overview.html')
def bills_overview(request):
    def build_info():
        # feeds about all legislation that we offer the user to subscribe to
        feeds = [f for f in Feed.get_simple_feeds() if f.category == "federal-bills"]

        # info about bills by status
        groups = [
            (   g[0], # title
                g[1], # noun
                g[2], # continuation text
               load_bill_status_search_link(None, g[4]),
               load_bill_status_qs(g[4]).count(), # count in category
               [getattr(sr, 'object', sr) for sr in load_bill_status_qs(g[4]).order_by('-current_status_date')[0:6]], # top 6 in this category, convert Haystack results to bills if they are Haystack results
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
            [0:12]
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
                  "link": load_bill_status_search_link(c, g[4])
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
    if width < 0 or width > 512: raise Http404()

    # We're going to display this next to photos of members of congress,
    # so use that aspect ratio by default.
    try:
        aspect = float(request.GET["aspect"])
    except:
        aspect = 240.0/200.0
    if image_type == "card": aspect = .5 # height/width

    # Rasterizes a page of a PDF to a greyscale PIL.Image.
    # Crop out the GPO seal & the vertical margins.
    def pdftopng(pdf_bytes, pagenumber, width=900):
        from PIL import Image
        import subprocess, io
        pngbytes = subprocess.check_output(["/usr/bin/pdftoppm", "-f", str(pagenumber), "-l", str(pagenumber), "-scale-to", str(width), "-png", "-"],
            input=pdf_bytes)
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
        if bbox:
            im = im.crop( (0, max(0, bbox[1]-vpad), im.size[0], min(im.size[1], bbox[3]+vpad) ) )

        return im

    # Find the PDF file and rasterize the first two pages.

    textversion = request.GET.get("textversion") # usually None
    if textversion and not re.match("^[a-z0-9-]+$", textversion): raise Http404()

    try:
        metadata = load_bill_text(bill, textversion, mods_only=True)
    except IOError:
        # if bill text metadata isn't available, we won't show the bill text as a part of the thumbnail
        metadata = None

    cache_fn = None

    from PIL import Image

    if not metadata or not metadata.get("thumbnail_base_path"):
        # Start with a blank page.
        w = max(width, 100)
        pg1 = Image.new("RGB", (w, int(aspect*w)), color=(255,255,255))
        pg2 = pg1
    else:
        # Check if we have a cached file. We want to cache longer than our HTTP cache
        # because these thumbnails basically never change and calling pdftoppm is expensive.
        # But see run_scrapers.py for how we can periodically delete old thumbnail files
        # because they take up a ton of disk space.
        import os.path
        cache_fn = metadata["thumbnail_base_path"] + "-" + image_type + "_" + str(width) + "_" + str(round(aspect,3)) + ".png"
        if os.path.exists(cache_fn):
            with open(cache_fn, "rb") as f:
                return HttpResponse(f.read(), content_type="image/png")

        # Use the PDF files on disk, or extract from the package.zip file, or download the PDF on the fly.
        if metadata.get("pdf_file"):
            with open(metadata["pdf_file"], 'rb') as f:
                pdf_bytes = f.read()
        elif metadata.get("govinfo_package_file"):
            import zipfile
            with zipfile.ZipFile(metadata["govinfo_package_file"]) as zf:
                for n in zf.namelist():
                    if re.search(r"/pdf/.*.pdf$", n):
                        pdf_bytes = zf.read(n)
                        break
                else:
                    # No PDF is available.
                    raise Http404()
        elif settings.DEBUG and metadata.get("gpo_pdf_url"):
            # When debugging in a local environment we may not have bill text available
            # so download the PDF from GPO.
            import os, tempfile, subprocess
            pdf_bytes = subprocess.check_output(["/usr/bin/wget", "-O", "-", "-q", metadata["gpo_pdf_url"]])
        else:
            # No PDF is available.
            raise Http404()

        pg1 = pdftopng(pdf_bytes, 1)
        try:
            pg2 = pdftopng(pdf_bytes, 2)
        except:
            pg2 = pg1.crop((0, 0, pg1.size[0], 0)) # may only be one page!


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
        img.thumbnail((width, int(aspect*width)), Image.LANCZOS)

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
    }


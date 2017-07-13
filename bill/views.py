# -*- coding: utf-8 -*-
from django.shortcuts import redirect, get_object_or_404
from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.conf import settings
from django.contrib.humanize.templatetags.humanize import ordinal
from django.contrib.auth.decorators import login_required
from django.db.models import Count, F
from django.core.cache import cache

from common.decorators import render_to
from common.pagination import paginate

from bill.models import Bill, BillType, BillStatus, BillTerm, TermType, BillTextComparison, BillSummary
from bill.search import bill_search_manager, parse_bill_citation
from bill.title import get_secondary_bill_title
from committee.util import sort_members
from person.models import Person
from events.models import Feed

from settings import CURRENT_CONGRESS

from us import get_congress_dates

import urllib, urllib2, json, datetime, re
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
    bill = load_bill_from_url(congress, type_slug, number)
    return {
        'bill': bill,
        "congressdates": get_congress_dates(bill.congress),
        "subtitle": get_secondary_bill_title(bill, bill.titles),
        "current": bill.congress == CURRENT_CONGRESS,
        "dead": bill.congress != CURRENT_CONGRESS and bill.current_status not in BillStatus.final_status_obvious,
        "feed": bill.get_feed(),
        "text_info": bill.get_text_info(with_citations=True),
        "text_incorporation": fixup_text_incorporation(bill.text_incorporation),
    }

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
    return map(fixup_item, text_incorporation)

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
                <br/>{{num_issuepos}} poll responses, {{num_calls}} phone calls to Congress.
            </div>
            """

        from poll_and_call.models import RelatedBill as IssueByBill
        try:
            from poll_and_call.models import *
            ix = RelatedBill.objects.get(bill=bill).issue
            num_issuepos = UserPosition.objects.filter(position__issue=ix).count()
            num_calls = len([c for c in CallLog.objects.filter(position__position__issue=ix) if c.is_complete()])
        except IssueByBill.DoesNotExist:
            num_issuepos = 0
            num_calls = 0

        from django.template import Template, Context, RequestContext, loader
        ret["admin_panel"] = Template(admin_panel).render(RequestContext(request, {
            'bill': bill,
            "feed": bill.get_feed(),
            "num_issuepos": num_issuepos,
            "num_calls": num_calls,
            }))

    from person.views import render_subscribe_inline
    ret.update(render_subscribe_inline(request, bill.get_feed()))

    # poll_and_call
    if request.user.is_authenticated():
        from poll_and_call.models import RelatedBill as IssueByBill, UserPosition
        try:
            issue = IssueByBill.objects.get(bill=bill).issue
            try:
                up = UserPosition.objects.get(user=request.user, position__issue=issue)
                targets = up.get_current_targets()
                ret["poll_and_call_position"] =  {
                    "id": up.position.id,
                    "text": up.position.text,
                    "can_change": up.can_change_position(),
                    "can_call": [(t.id, t.person.name) for t in targets] if isinstance(targets, list) else [],
                    "call_url": issue.get_absolute_url() + "/make_call",
                }
            except UserPosition.DoesNotExist:
                pass
        except IssueByBill.DoesNotExist:
            pass

    # emoji reactions
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
    ret["reactions"] = [ ]
    for emoji in Reaction.EMOJI_CHOICES:
        ret["reactions"].append({
            "name": emoji,
            "count": emoji_counts.get(emoji, 0),
            "me": emoji in my_emojis,
        })
    # stable sort by count so that zeroes are in our preferred order
    ret["reactions"] = sorted(ret["reactions"], key = lambda x : -x["count"])

    return ret

@anonymous_view
@render_to("bill/bill_summaries.html")
def bill_summaries(request, congress, type_slug, number):
    bill = load_bill_from_url(congress, type_slug, number)
    return {
        "bill": bill,
        "congressdates": get_congress_dates(bill.congress),
        "text_info": bill.get_text_info(with_citations=True), # for the header tabs
    }

@anonymous_view
@render_to("bill/bill_full_details.html")
def bill_full_details(request, congress, type_slug, number):
    bill = load_bill_from_url(congress, type_slug, number)
    return {
        "bill": bill,
        "related": get_related_bills(bill),
        "text_info": bill.get_text_info(with_citations=True), # for the header tabs
    }

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
    from django.shortcuts import render_to_response
    from django.template import RequestContext
    return render_to_response("bill/bill_widget.js", { "bill": bill, "SITE_ROOT_URL": settings.SITE_ROOT_URL }, context_instance=RequestContext(request), content_type="text/javascript" )

@anonymous_view
@render_to("bill/bill_widget_info.html")
def bill_widget_info(request, congress, type_slug, number):
    bill = load_bill_from_url(congress, type_slug, number)
    return {
        "bill": bill,
        "SITE_ROOT_URL": settings.SITE_ROOT_URL,
    }

@json_response
@login_required
def market_test_vote(request):
    bill = get_object_or_404(Bill, id = request.POST.get("bill", "0"))
    prediction = int(request.POST.get("prediction", "0"))
    market = bill.get_open_market(request.user)
    if not market: return { }

    from predictionmarket.models import Trade, TradingAccount
    account = TradingAccount.get(request.user)
    if prediction != 0:
        # Buy shares in one of the outcomes.
        try:
            t = Trade.place(account, market.outcomes.get(owner_key = 1 if prediction == 1 else 0), 10)
        except ValueError as e:
            return { "error": str(e) }

    else:
        # Sell shares.
        positions, pl = account.position_in_market(market)
        for outcome in positions:
            Trade.place(account, outcome, -positions[outcome]["shares"])

    return { "vote": prediction }

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

    from billtext import load_bill_text, get_bill_text_versions
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
    from billtext import get_current_version
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

@anonymous_view
@json_response
def bill_text_ajax(request):
    for p in ("left_bill", "left_version", "right_bill", "right_version", "mode"):
        if not p in request.GET:
            raise Http404()

    try:
        return load_comparison(request.GET["left_bill"], request.GET["left_version"], request.GET["right_bill"], request.GET["right_version"])
    except IOError as e:
        return { "error": str(e) }

def load_comparison(left_bill, left_version, right_bill, right_version, timelimit=10, use_cache=True, force_update=False):
    from billtext import load_bill_text, get_current_version
    from xml_diff import compare
    import lxml

    left_bill = Bill.objects.get(id = left_bill)
    right_bill = Bill.objects.get(id = right_bill)

    if left_version == "": left_version = get_current_version(left_bill)
    if right_version == "": right_version = get_current_version(right_bill)

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
    def differ(text1, text2):
        # ensure we use the C++ Google DMP and can specify the time limit
        import diff_match_patch
        for x in diff_match_patch.diff_unicode(text1, text2, timelimit=timelimit):
            yield x
    compare(doc1.getroot(), doc2.getroot(), make_tag_func=make_tag_func, differ=differ)

    # Prepare JSON response data.
        # dates aren't JSON serializable
    left["docdate"] = left["docdate"].strftime("%x")
    right["docdate"] = right["docdate"].strftime("%x")
    ret = {
        "left_meta": left,
        "right_meta": right,
        "left_text": lxml.etree.tostring(doc1),
        "right_text": lxml.etree.tostring(doc2),
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
        ix = BillTerm.objects.get(id=request.GET["subject"])
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

    url = "https://www.popvox.com/api/" + method + "?" + urllib.urlencode(_args).encode("utf8")

    req = urllib2.Request(url)
    resp = urllib2.urlopen(req)
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
        for t in BillTerm.objects.filter(term_type=TermType.new).exclude(parents__id__gt=0):
            x = []
            subject_choices_data[t] = x
            for tt in t.subterms.all():
                x.append(tt)
        subject_choices_data = sorted(subject_choices_data.items(), key = lambda x : x[0].name)
    return subject_choices_data

# used by bill_docket and bill_statistics
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
@render_to('bill/bill_docket.html')
def bill_docket(request):
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

        return {
            "feeds": feeds,

            "total": Bill.objects.filter(congress=CURRENT_CONGRESS).count(),
            "current_congress": CURRENT_CONGRESS,
            "current_congress_dates": get_congress_dates(CURRENT_CONGRESS),

            "groups": groups,
            "coming_up": coming_up,
            "top_tracked_bills": top_bills,

            "subjects": subject_choices(),
            "BILL_STATUS_INTRO": (BillStatus.introduced, BillStatus.reported),
        }

    ret = cache.get("bill_docket_info")
    if not ret:
        ret = build_info()
        cache.set("bill_docket_info", ret, 60*60)

    return ret

@anonymous_view
@render_to('bill/bill_statistics.html')
def bill_statistics(request):
    # Get the count of bills by status and by Congress.
    counts_by_congress = []
    for c in xrange(93, CURRENT_CONGRESS+1):
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
def start_poll(request):
    from poll_and_call.models import Issue, IssuePosition, RelatedBill as IssueByBill

    # get the bill & valence
    bill = get_object_or_404(Bill, id=request.GET.get("bill"))
    valence = (request.GET.get("position") == "support")

    # get the Issue
    try:
        ix = IssueByBill.objects.get(bill=bill).issue
    except IssueByBill.DoesNotExist:
        # no Issue yet, so create
        ix = Issue.objects.create(
            slug = "%d-%s-%d" % (bill.congress, bill.bill_type_slug, bill.number),
            title = "PLACEHOLDER",
            question = "PLACEHOLDER",
            introtext = "Weigh in on %s." % bill.display_number_with_congress_number,
            isopen = True,
            )
        IssueByBill.objects.create(issue=ix, bill=bill, valence=True)

    # update the Issue since the bill title may have changed
    ix.title = bill.title
    ix.question = "What is your position on %s?" % bill.title
    ix.save()

    # how to refer to the bill in the call script
    from django.template.defaultfilters import truncatewords
    title = bill.title_no_number
    if re.match(".* Act( of \d{4})?", title):
        title = "The " + title
    title = bill.display_number + ": " + title
    bt = truncatewords(title, 11)
    if "..." in bt:
        bt = truncatewords(title, 15)
        bt = u"%s (\u201C%s\u201D)" % (bill.display_number, bt.replace(bill.display_number + ": ", ""))

    # create and update the options
    for opt_valence, opt_verb in ((True, "support"), (False, "oppose")):
        try:
            p = ix.positions.get(valence=opt_valence)
        except:
            p = IssuePosition.objects.create(
                    text="PLACEHOLDER",
                    valence=opt_valence,
                    call_script="PLACEHOLDER",
                    )
            ix.positions.add(p)

        p.text = opt_verb.title()
        p.call_script = "I %s %s." % (opt_verb, bt)
        p.save()

    return HttpResponseRedirect(ix.get_absolute_url() + "/join/" + str(ix.positions.get(valence=valence).id))

@anonymous_view
def bill_text_image(request, congress, type_slug, number, image_type):
    bill = load_bill_from_url(congress, type_slug, number)
    from billtext import load_bill_text

    # Rasterizes a page of a PDF to a greyscale PIL.Image.
    # Crop out the GPO seal & the vertical margins.
    def pdftopng(pdffile, pagenumber, width=900):
        from PIL import Image
        import subprocess, StringIO
        pngbytes = subprocess.check_output(["/usr/bin/pdftoppm", "-f", str(pagenumber), "-l", str(pagenumber), "-scale-to", str(width), "-png", pdffile])
        im = Image.open(StringIO.StringIO(pngbytes))
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
        # if bill text metadata isn't available, trap the error
        # and just 404 it
        raise Http404()

    if metadata.get("pdf_file"):
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
    
    from PIL import Image
    img = Image.new(pg1.mode, (pg1.size[0], int(pg1.size[1]+pg2.size[1])))
    img.paste(pg1, (0,0))
    img.paste(pg2, (0,pg1.size[1]))

    # Zealous crop the (horizontal) margins. We do this only after the two
    # pages have been combined so that we don't mess up their alignment.
    # Add some padding.
    from PIL import ImageOps
    hpad = int(.02*img.size[0])
    bbox = ImageOps.invert(img).getbbox()
    img = img.crop( (max(0, bbox[0]-hpad), 0, min(img.size[0], bbox[2]+hpad), img.size[1]) )

    # Now take a window from the top matching a particular aspect ratio.
    # We're going to display this next to photos of members of congress,
    # so use that aspect ratio.
    try:
        aspect = float(request.GET["aspect"])
    except:
	    aspect = 240.0/200.0
    img = img.crop((0,0, img.size[0], int(aspect*img.size[0])))

    # Resize to requested width.
    if "width" in request.GET:
        img.thumbnail((int(request.GET["width"]), int(aspect*float(request.GET["width"]))), Image.ANTIALIAS)

    # Add symbology.
    if image_type == "thumbnail":
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

    # Serialize & return.
    import StringIO
    imgbytesbuf = StringIO.StringIO()
    img.save(imgbytesbuf, "PNG")
    imgbytes = imgbytesbuf.getvalue()
    imgbytesbuf.close()
    return HttpResponse(imgbytes, content_type="image/png")

@anonymous_view
def bill_get_json(request, congress, type_slug, number):
    bill = load_bill_from_url(congress, type_slug, number)
    return HttpResponseRedirect("/api/v2/bill/%d" % bill.id)
     


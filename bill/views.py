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

import urllib, urllib2, json, datetime, os.path, re
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

@anonymous_view
@render_to('bill/bill_details.html')
def bill_details(request, congress, type_slug, number):
    bill = load_bill_from_url(congress, type_slug, number)

    from person.name import get_person_name
    sponsor_name = None if not bill.sponsor else \
        get_person_name(bill.sponsor, role_date=bill.introduced_date, firstname_position='before', show_suffix=True)

    def get_reintroductions():
        reintro_prev = None
        reintro_next = None
        for reintro in bill.find_reintroductions():
            if reintro.congress < bill.congress: reintro_prev = reintro
            if reintro.congress > bill.congress and not reintro_next: reintro_next = reintro
        return reintro_prev, reintro_next

    def get_text_info():
        from models import USCSection
        from billtext import load_bill_text
        from search import parse_slip_law_number
        import re
        try:
            metadata = load_bill_text(bill, None, mods_only=True)

            # do interesting stuff with citations
            if "citations" in metadata and not settings.DEBUG:
                slip_laws = []
                statutes = []
                usc = { }
                other = []
                usc_other = USCSection(name="Other Citations", ordering=99999)
                for cite in metadata["citations"]:
                    if cite["type"] == "slip_law":
                        slip_laws.append(cite)
                        cite["bill"] = parse_slip_law_number(cite["text"])
                    elif cite["type"] == "statutes_at_large":
                        statutes.append(cite)
                    elif cite["type"] in ("usc-section", "usc-chapter"):
                        # Build a tree of title-chapter-...-section nodes so we can
                        # display the citations in context.
                        try:
                            sec_obj = USCSection.objects.get(citation=cite["key"])
                        except: # USCSection.DoesNotExist and MultipleObjectsReturned both possible
                            # create a fake entry for the sake of output
                            # the 'id' field is set to make these objects properly hashable
                            sec_obj = USCSection(id=cite["text"], name=cite["text"], parent_section=usc_other)

                        if "range_to_section" in cite:
                            sec_obj.range_to_section = cite["range_to_section"]

                        # recursively go up to the title
                        path = [sec_obj]
                        so = sec_obj
                        while so.parent_section:
                            so = so.parent_section
                            path.append(so)

                        # build a link to LII
                        if cite["type"] == "usc-section":
                            cite_link = "http://www.law.cornell.edu/uscode/text/" + cite["title"]
                            if cite["section"]:
                                cite_link += "/" + cite["section"]
                            if cite["paragraph"]: cite_link += "#" + "_".join(re.findall(r"\(([^)]+)\)", cite["paragraph"]))
                        elif cite["type"] == "usc-chapter":
                            cite_link = "http://www.law.cornell.edu/uscode/text/" + cite["title"] + "/" + "/".join(
                                (so.level_type + "-" + so.number) for so in reversed(path[:-1])
                                )
                        sec_obj.link = cite_link

                        # now pop off from the path to put the node at the right point in a tree
                        container = usc
                        while path:
                            p = path.pop(-1)
                            if p not in container: container[p] = { }
                            container = container[p]

                    else:
                        other.append(cite)

                slip_laws.sort(key = lambda x : (x["congress"], x["number"]))

                # restructure data format
                def ucfirst(s): return s[0].upper() + s[1:]
                def rebuild_usc_sec(seclist, indent=0):
                    ret = []
                    seclist = sorted(seclist.items(), key=lambda x : x[0].ordering)
                    for sec, subparts in seclist:
                        ret.append({
                            "text": (ucfirst(sec.level_type + ((" " + sec.number) if sec.number else "") + (": " if sec.name else "")) if sec.level_type else "") + (sec.name_recased if sec.name else ""),
                            "link": getattr(sec, "link", None),
                            "range_to_section": getattr(sec, "range_to_section", None),
                            "indent": indent,
                        })
                        ret.extend(rebuild_usc_sec(subparts, indent=indent+1))
                    return ret
                usc = rebuild_usc_sec(usc)

                metadata["citations"] = {
                    "slip_laws": slip_laws, "statutes": statutes, "usc": usc, "other": other,
                    "count": len(slip_laws)+len(statutes)+len(usc)+len(other) }
            return metadata
        except IOError:
            return None

    return {
        'bill': bill,
        "congressdates": get_congress_dates(bill.congress),
        "subtitle": get_secondary_bill_title(bill, bill.titles),
        "sponsor_name": sponsor_name,
        "reintros": get_reintroductions, # defer so we can use template caching
        "current": bill.congress == CURRENT_CONGRESS,
        "dead": bill.congress != CURRENT_CONGRESS and bill.current_status not in BillStatus.final_status_obvious,
        "feed": Feed.BillFeed(bill),
        "text": get_text_info,

        "care2_category_id": {
            5816: '793', # Agriculture and Food=>Health
            5840: '789', # Animals=>Animal Welfare
            5996: '794', # Civil Rights=>Human Rights
            5991: '791', # Education=>Education
            6021: '792', # Energy=>Environment & Wildlife
            6038: '792', # Environmental Protection=>Environment & Wildlife
            6053: '793', # Families=>Health
            6130: '793', # Health=>Health
            6206: '794', # Immigration=>Human Rights
            6279: '792', # Public Lands/Natural Resources=>Environment & Wildlife
            6321: '791', # Social Sciences=>Education
            6328: '793', # Social Welfare => Health
        }.get(bill.get_top_term_id(), '795') # fall back to Politics category
    }

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
                <br/>Tracked by {{feed.tracked_in_lists.count|intcomma}} users
                ({{feed.tracked_in_lists_with_email.count|intcomma}} w/ email).
            </div>
            """
        from django.template import Template, Context, RequestContext, loader
        ret["admin_panel"] = Template(admin_panel).render(RequestContext(request, {
            'bill': bill,
            "feed": Feed.BillFeed(bill),
            }))

    from person.views import render_subscribe_inline
    ret.update(render_subscribe_inline(request, Feed.BillFeed(bill)))

    # poll_and_call
    if request.user.is_authenticated():
        from poll_and_call.models import RelatedBill as IssueByBill, UserPosition
        try:
            issue = IssueByBill.objects.get(bill=bill).issue
            try:
                up = UserPosition.objects.get(user=request.user, position__issue=issue)
                ret["poll_and_call_position"] =  {
                    "id": up.position.id,
                    "text": up.position.text,
                    "can_change": up.can_change_position(),
                    "can_call": up.can_make_call(),
                    "call_url": issue.get_absolute_url() + "/make_call",
                }
            except UserPosition.DoesNotExist:
                pass
        except IssueByBill.DoesNotExist:
            pass
        
    return ret

@anonymous_view
@render_to("bill/bill_widget.html")
def bill_widget(request, congress, type_slug, number):
    bill = load_bill_from_url(congress, type_slug, number)

    from person.name import get_person_name
    sponsor_name = None if not bill.sponsor else \
        get_person_name(bill.sponsor, role_date=bill.introduced_date, firstname_position='before', show_suffix=True)

    def get_text_info():
        from billtext import load_bill_text
        try:
            return load_bill_text(bill, None, mods_only=True)
        except IOError:
            return None

    return {
        "SITE_ROOT_URL": settings.SITE_ROOT_URL,
        "bill": bill,
        "congressdates": get_congress_dates(bill.congress),
        "subtitle": get_secondary_bill_title(bill, bill.titles),
        "sponsor_name": sponsor_name,
        "current": bill.congress == CURRENT_CONGRESS,
        "dead": bill.congress != CURRENT_CONGRESS and bill.current_status not in BillStatus.final_status_obvious,
        "text": get_text_info,
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

    from billtext import load_bill_text, bill_gpo_status_codes
    try:
        textdata = load_bill_text(bill, version)
    except IOError:
        textdata = None

    # Get a list of the alternate versions of this bill.
    alternates = None
    if textdata:
        alternates = []
        for v in bill_gpo_status_codes:
            fn = "data/us/bills.text/%s/%s/%s%d%s.mods.xml" % (bill.congress, BillType.by_value(bill.bill_type).xml_code, BillType.by_value(bill.bill_type).xml_code, bill.number, v)
            if os.path.exists(fn):
                alternates.append(load_bill_text(bill, v, mods_only=True))
        alternates.sort(key = lambda mods : mods["docdate"])

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
        "alternates": alternates,
        "related_bills": related_bills,
    }

@anonymous_view
@json_response
def bill_text_ajax(request):
    for p in ("left_bill", "left_version", "right_bill", "right_version", "mode"):
        if not p in request.GET:
            raise Http404()

    try:
        return load_comparison(request.GET["left_bill"], request.GET["left_version"], request.GET["right_bill"], request.GET["right_version"])
    except IOError:
        return { "error": "Bill text is not available for those bills." }

def load_comparison(left_bill, left_version, right_bill, right_version, timelimit=10, force=False):
    from billtext import load_bill_text, compare_xml_text, get_current_version
    import lxml

    left_bill = Bill.objects.get(id = left_bill)
    right_bill = Bill.objects.get(id = right_bill)

    if left_version == "": left_version = get_current_version(left_bill)
    if right_version == "": right_version = get_current_version(right_bill)

    btc = None
    try:
        btc = BillTextComparison.objects.get(
            bill1 = left_bill,
            ver1 = left_version,
            bill2 = right_bill,
            ver2 = right_version)
        btc.decompress()
        if not force: return btc.data
    except BillTextComparison.DoesNotExist:
        pass

    # Try with the bills swapped.
    try:
        btc2 = BillTextComparison.objects.get(
            bill2 = left_bill,
            ver2 = left_version,
            bill1 = right_bill,
            ver1 = right_version)
        btc2.decompress()
        data = btc2.data
        return {
            "left_meta": data["right_meta"],
            "right_meta": data["left_meta"],
            "left_text": data["right_text"],
            "right_text": data["left_text"],
        }
    except BillTextComparison.DoesNotExist:
        pass

    left = load_bill_text(left_bill, left_version, mods_only=True)
    right = load_bill_text(right_bill, right_version, mods_only=True)

    doc1 = lxml.etree.parse(left["basename"] + ".html")
    doc2 = lxml.etree.parse(right["basename"] + ".html")
    compare_xml_text(doc1, doc2, timelimit=timelimit) # revises DOMs in-place

    # dates aren't JSON serializable
    left["docdate"] = left["docdate"].strftime("%x")
    right["docdate"] = right["docdate"].strftime("%x")

    ret = {
        "left_meta": left,
        "right_meta": right,
        "left_text": lxml.etree.tostring(doc1),
        "right_text": lxml.etree.tostring(doc2),
    }

    if not btc:
        btc = BillTextComparison(
            bill1 = left_bill,
            ver1 = left_version,
            bill2 = right_bill,
            ver2 = right_version,
            data = dict(ret)) # clone before compress()
    else:
        btc.data = dict(ret) # clone before compress()

    btc.compress()
    btc.save()

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
    return bill_search_manager().view(request, template,
        defaults={
            "congress": request.GET["congress"] if "congress" in request.GET else (CURRENT_CONGRESS if "sponsor" not in request.GET else None), # was Person.objects.get(id=request.GET["sponsor"]).most_recent_role_congress(), but we can just display the whole history which is better at the beginning of a Congress when there are no bills
            "sponsor": request.GET.get("sponsor", None),
            "terms": ix1.id if ix1 else None,
            "terms2": ix2.id if ix2 else None,
            "text": request.GET.get("text", None),
            "current_status": request.GET.get("status").split(",") if "status" in request.GET else None,
            "sort": request.GET.get("sort", None if "sponsor" not in request.GET else "-introduced_date"),
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
def subject_choices(include_legacy=True):
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
        BillStatus.final_status_passed_bill), # 2
    ("Passed Resolutions",
        "passed resolutions", " so far in this session of Congress (for joint and concurrent resolutions, passed both chambers)", " (for joint and concurrent resolutions, this means passed both chambers)",
        BillStatus.final_status_passed_resolution), # 3
    ("Got A Vote",
        "bills and joint/concurrent resolutions", " that had a significant vote in one chamber, making them likely to have further action", " that had a significant vote in one chamber",
        (BillStatus.pass_over_house, BillStatus.pass_over_senate, BillStatus.pass_back_senate, BillStatus.pass_back_house, BillStatus.passed_bill)), # 5
    ("Failed Legislation",
        "bills and resolutions", " that failed a vote on passage and are now dead or failed a significant vote such as cloture, passage under suspension, or resolving differences", " that failed a vote on passage or failed a significant vote such as cloture, passage under suspension, or resolving differences",
        (BillStatus.fail_originating_house, BillStatus.fail_originating_senate, BillStatus.fail_second_house, BillStatus.fail_second_senate, BillStatus.prov_kill_suspensionfailed, BillStatus.prov_kill_cloturefailed, BillStatus.prov_kill_pingpongfail)), # 7
    ("Vetoed Bills (w/o Override)",
        "bills", " that were vetoed and the veto was not overridden by Congress", " that were vetoed and the veto was not overridden by Congress",
        (BillStatus.prov_kill_veto, BillStatus.override_pass_over_house, BillStatus.override_pass_over_senate, BillStatus.vetoed_pocket, BillStatus.vetoed_override_fail_originating_house, BillStatus.vetoed_override_fail_originating_senate, BillStatus.vetoed_override_fail_second_house, BillStatus.vetoed_override_fail_second_senate)), # 8
    ("Other Legislation",
        "bills and resolutions", " that have been introduced, referred to committee, or reported by committee and await further action", " that were introduced, referred to committee, or reported by committee but had no further action",
        (BillStatus.introduced, BillStatus.referred, BillStatus.reported)), # 3
]

def load_bill_status_qs(statuses, congress=CURRENT_CONGRESS):
    return Bill.objects.filter(congress=congress, current_status__in=statuses)

@anonymous_view
@render_to('bill/bill_docket.html')
def bill_docket(request):
    def build_info():
        feeds = [f for f in Feed.get_simple_feeds() if f.category == "federal-bills"]

        groups = [
            (   g[0], # title
                g[1], # text 1
                g[2], # text 2
                "/congress/bills/browse?status=" + ",".join(str(s) for s in g[4]), # link
               load_bill_status_qs(g[4]).count(), # count in category
               load_bill_status_qs(g[4]).order_by('-current_status_date')[0:6], # top 6 in this category
                )
            for g in bill_status_groups ]

        dhg_bills = Bill.objects.filter(congress=CURRENT_CONGRESS, docs_house_gov_postdate__gt=datetime.datetime.now() - datetime.timedelta(days=10)).filter(docs_house_gov_postdate__gt=F('current_status_date'))
        sfs_bills = Bill.objects.filter(congress=CURRENT_CONGRESS, senate_floor_schedule_postdate__gt=datetime.datetime.now() - datetime.timedelta(days=5)).filter(senate_floor_schedule_postdate__gt=F('current_status_date'))
        coming_up = list(dhg_bills | sfs_bills)
        coming_up.sort(key = lambda b : b.docs_house_gov_postdate if (b.docs_house_gov_postdate and (not b.senate_floor_schedule_postdate or b.senate_floor_schedule_postdate < b.docs_house_gov_postdate)) else b.senate_floor_schedule_postdate, reverse=True)

        start, end = get_congress_dates(CURRENT_CONGRESS)
        end_year = end.year if end.month > 1 else end.year-1 # count January finishes as the prev year
        current_congress_years = '%d-%d' % (start.year, end.year)
        current_congress = ordinal(CURRENT_CONGRESS)

        return {
            "feeds": feeds,

            "total": Bill.objects.filter(congress=CURRENT_CONGRESS).count(),
            "current_congress_years": current_congress_years,
            "current_congress": current_congress,
            "groups": groups,
            "coming_up": coming_up,
            "subjects": subject_choices(),
            "BILL_STATUS_INTRO": (BillStatus.introduced, BillStatus.referred, BillStatus.reported),
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
        cursor = connection.cursor()
        def pull_time_stat(field, where, historical=True):
            cursor.execute("SELECT YEAR(%s) - congress*2 - 1787, MONTH(%s), COUNT(*) FROM bill_bill WHERE congress>=93 AND congress%s%d AND %s GROUP BY YEAR(%s) - congress*2, MONTH(%s)" % (field, field, "<" if historical else "=", CURRENT_CONGRESS, where, field, field))
            activity = [{ "x": r[0]*12 + (r[1]-1), "count": r[2], "year": r[0] } for r in cursor.fetchall()]
            total = sum(m["count"] for m in activity)
            for i, m in enumerate(activity): m["cumulative_count"] = m["count"]/float(total) + (0.0 if i==0 else activity[i-1]["cumulative_count"])
            for m in activity: m["count"] = round(m["count"] / (CURRENT_CONGRESS-96), 1)
            for m in activity: m["cumulative_count"] = round(m["cumulative_count"] * 100.0)
            return activity
        activity_introduced_by_month = pull_time_stat('introduced_date', "1")
        activity_enacted_by_month = pull_time_stat('current_status_date', "current_status IN (%d,%d)" % (int(BillStatus.enacted_signed), int(BillStatus.enacted_veto_override)))
    else:
        activity_introduced_by_month = []
        activity_enacted_by_month = []

    return {
        "groups2": bill_status_groups,
        "counts_by_congress": counts_by_congress,
        "activity": (("Bills and Resolutions Introduced", activity_introduced_by_month),
         ("Bills and Joint Resolutions Enacted", activity_enacted_by_month) )
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
    return show_bill_browse("bill/subject.html", request, ix1, ix2, { "term": ix, "feed": Feed.IssueFeed(ix) })

@user_view_for(subject)
def subject_user_view(request, sluggedname, termid):
    ix = get_object_or_404(BillTerm, id=termid)
    ret = { }
    from person.views import render_subscribe_inline
    ret.update(render_subscribe_inline(request, Feed.IssueFeed(ix)))
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
            title = bill.title,
            question = "What is your position on %s?" % bill.title,
            introtext = "Weigh in on %s." % bill.display_number_with_congress_number,
            isopen = True,
            )
        IssueByBill.objects.create(issue=ix, bill=bill, valence=True)

        # how to refer to the bill
        from django.template.defaultfilters import truncatewords
        bt = truncatewords(bill.title, 8)
        if "..." not in bt:
            bt = truncatewords(bill.title, 11)
        else:
            bt = u"%s (\u201C%s\u201D)" % (bill.display_number, bt)
        ix.positions.add(IssuePosition.objects.create(
            text="Support",
            valence=True,
            call_script="I support %s." % bt,
            ))
        ix.positions.add(IssuePosition.objects.create(
            text="Oppose",
            valence=False,
            call_script="I oppose %s." % bt,
            ))

    return HttpResponseRedirect(ix.get_absolute_url() + "/join/" + str(ix.positions.get(valence=valence).id))

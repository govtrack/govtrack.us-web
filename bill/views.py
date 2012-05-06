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

from bill.models import Bill, BillType, BillStatus, BillTerm, TermType
from bill.search import bill_search_manager, parse_bill_number
from bill.title import get_secondary_bill_title
from committee.models import CommitteeMember, CommitteeMemberRole
from committee.util import sort_members
from person.models import Person
from events.models import Feed

from settings import CURRENT_CONGRESS

from us import get_congress_dates

import urllib, urllib2, json, datetime, re
from registration.helpers import json_response

@render_to('bill/bill_details.html')
def bill_details(request, congress, type_slug, number):
    if type_slug.isdigit():
        bill_type = type_slug
    else:
        try:
            bill_type = BillType.by_slug(type_slug)
        except BillType.NotFound:
            raise Http404("Invalid bill type: " + type_slug)
    
    bill = get_object_or_404(Bill, congress=congress, bill_type=bill_type, number=number)
    
    def get_prognosis():
        if bill.congress != CURRENT_CONGRESS: return None
        import prognosis
        prog = prognosis.compute_prognosis(bill)
        prog["congressdates"] = get_congress_dates(prog["congress"])
        return prog
        
    def get_reintroductions():
        reintro_prev = None
        reintro_next = None
        def normalize_title(title):
            # remove anything that looks like a year
            return re.sub(r"of \d\d\d\d$", "", title)
        for reintro in Bill.objects.exclude(congress=bill.congress).filter(sponsor=bill.sponsor).order_by('congress'):
            if normalize_title(bill.title_no_number) != normalize_title(reintro.title_no_number): continue
            if reintro.congress < bill.congress: reintro_prev = reintro
            if reintro.congress > bill.congress and not reintro_next: reintro_next = reintro
        return reintro_prev, reintro_next
        
    def get_market():
        m = bill.get_open_market(request.user)
        if m: m.name = m.name.replace(bill.display_number, "it")
        return m
                                                    
    return {
        'bill': bill,
        "congressdates": get_congress_dates(bill.congress),
        "subtitle": get_secondary_bill_title(bill, bill.titles),
        "prognosis": get_prognosis, # defer so we can use template caching
        "reintros": get_reintroductions, # defer so we can use template caching
        "market": get_market,
        "current": bill.congress == CURRENT_CONGRESS,
        "dead": bill.congress != CURRENT_CONGRESS and bill.current_status not in BillStatus.final_status_obvious,
        'feed': Feed.BillFeed(bill),
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

@render_to('bill/bill_text.html')
def bill_text(request, congress, type_slug, number):
    try:
        bill_type = BillType.by_slug(type_slug)
    except BillType.NotFound:
        raise Http404("Invalid bill type: " + type_slug)
    bill = get_object_or_404(Bill, congress=congress, bill_type=bill_type, number=number)
    
    try:
        from billtext import load_bill_text
        textdata = load_bill_text(bill, None)
    except IOError:
        textdata = None

    #from billtext import compare_xml_text
    #import lxml
    #doc1 = lxml.etree.parse("data/us/bills.text/112/h/h3606ih.html")
    #doc2 = lxml.etree.parse("data/us/bills.text/112/h/h3606rh.html")
    #compare_xml_text(doc1, doc2)
    #textdata["text_html"] = lxml.etree.tostring(doc1)
    #textdata["text_html_2"] = lxml.etree.tostring(doc2)

    return {
        'bill': bill,
        "congressdates": get_congress_dates(bill.congress),
        "textdata": textdata,
    }

def bill_list(request):
    if request.POST.get("allow_redirect", "") == "true":
        bill = parse_bill_number(request.POST.get("text", ""), congress=request.POST.get("congress", ""))
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
            "congress": request.GET["congress"] if "congress" in request.GET else (CURRENT_CONGRESS if "sponsor" not in request.GET else Person.objects.get(id=request.GET["sponsor"]).most_recent_role_congress()),
            "sponsor": request.GET.get("sponsor", None),
            "terms": ix1.id if ix1 else None,
            "terms2": ix2.id if ix2 else None,
            "text": request.GET.get("text", None),
            "current_status": request.GET.get("status").split(",") if "status" in request.GET else None,
            "sort": request.GET.get("sort", None),
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

@render_to('bill/bill_docket.html')
def bill_docket(request):
    def build_info():
        groups = [
            ("Successful Bills", "enacted bills", " so far in this session of Congress", BillStatus.final_status_passed_bill),
            ("Successful Resolutions", "passed resolutions", " so far in this session of Congress", BillStatus.final_status_passed_resolution),
            ("Active Bills", "bills", " that are awaiting the president's signature, have differences between the chambers to be resolved, or were vetoed", BillStatus.active_status),
            ("Waiting Bills", "bills and resolutions", " that had a significant vote in one chamber and are likely to get a vote in the other chamber", BillStatus.waiting_status),
            ("Inactive Bills", "bills and resolutions", " that have been introduced, referred to committee, or reported by committee and await further action", BillStatus.inactive_status),
            ("Unsuccessful Bills", "bills and resolutions", " that failed a vote and are now dead", BillStatus.final_status_failed),
        ]
        
        def loadgroupqs(statuses):
            return Bill.objects.filter(congress=CURRENT_CONGRESS, current_status__in=statuses)
        
        groups = [
            (   g[0], # title
                g[1], # text 1
                g[2], # text 2
                "/congress/bills/browse?status=" + ",".join(str(s) for s in g[3]), # link
               loadgroupqs(g[3]).count(), # count in category
               loadgroupqs(g[3]).order_by('-current_status_date')[0:6], # top 6 in this category
                )
            for g in groups ]
            
        dhg_bills = Bill.objects.filter(congress=CURRENT_CONGRESS, docs_house_gov_postdate__gt=datetime.datetime.now() - datetime.timedelta(days=10)).filter(docs_house_gov_postdate__gt=F('current_status_date'))
        sfs_bills = Bill.objects.filter(congress=CURRENT_CONGRESS, senate_floor_schedule_postdate__gt=datetime.datetime.now() - datetime.timedelta(days=5)).filter(senate_floor_schedule_postdate__gt=F('current_status_date'))
        coming_up = list(dhg_bills | sfs_bills)
        coming_up.sort(key = lambda b : b.docs_house_gov_postdate if (b.docs_house_gov_postdate and (not b.senate_floor_schedule_postdate or b.senate_floor_schedule_postdate < b.docs_house_gov_postdate)) else b.senate_floor_schedule_postdate, reverse=True)
        
        start, end = get_congress_dates(CURRENT_CONGRESS)
        end_year = end.year if end.month > 1 else end.year-1 # count January finishes as the prev year
        current_congress_years = '%d-%d' % (start.year, end.year)
        current_congress = ordinal(CURRENT_CONGRESS)     
        
        return {
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
    
def subject(request, sluggedname, termid):
    ix = BillTerm.objects.get(id=termid)
    if ix.parents.all().count() == 0:
        ix1 = ix
        ix2 = None
    else:
        ix1 = ix.parents.all()[0]
        ix2 = ix
    return show_bill_browse("bill/subject.html", request, ix1, ix2, { "term": ix, "feed": Feed.IssueFeed(ix) })
    
import django.contrib.sitemaps
class sitemap_current(django.contrib.sitemaps.Sitemap):
    changefreq = "weekly"
    priority = 1.0
    def items(self):
        return Bill.objects.filter(congress=CURRENT_CONGRESS)
class sitemap_previous(django.contrib.sitemaps.Sitemap):
    changefreq = "yearly"
    priority = 0.25
    def items(self):
        return Bill.objects.filter(congress=CURRENT_CONGRESS-1)
class sitemap_archive(django.contrib.sitemaps.Sitemap):
    changefreq = "yearly"
    priority = 0.25
    def items(self):
        return Bill.objects.filter(congress__lt=CURRENT_CONGRESS-1)
    

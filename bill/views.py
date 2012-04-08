# -*- coding: utf-8 -*-
from django.shortcuts import redirect, get_object_or_404
from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.conf import settings
from django.contrib.humanize.templatetags.humanize import ordinal
from django.contrib.auth.decorators import login_required
from django.db.models import Count
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

import urllib, urllib2, json, datetime, lxml
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
        
    # simple predictive market implementation
    from website.models import TestMarketVote
    from math import exp
    market_score = TestMarketVote.objects.filter(bill=bill).values("prediction").annotate(count=Count("prediction"))
    market_score = dict((int(x["prediction"]), x["count"]) for x in market_score)
    b = 5.0
    initial_no = 2.5
    initial_yes = 0 # use the prognosis info to add to this, but that's not currently working
    market_score = exp(initial_yes+market_score.get(1, 0)/b) / (exp(initial_no+market_score.get(-1, 0)/b) + exp(initial_yes+market_score.get(1, 0)/b))
    market_score = int(round(100*market_score))
    try:
        market_score_you = TestMarketVote.objects.get(user=request.user, bill=bill)
    except:
        market_score_you = None
        
    return {
        'bill': bill,
        "congressdates": get_congress_dates(bill.congress),
        "subtitle": get_secondary_bill_title(bill, bill.titles),
        "prognosis": get_prognosis, # defer so we can use template caching
        "current": bill.congress == CURRENT_CONGRESS,
        "dead": bill.congress != CURRENT_CONGRESS and bill.current_status not in BillStatus.final_status_obvious,
        'feed': Feed.BillFeed(bill),
        #"market_score": market_score,
        #"market_score_you": market_score_you,
    }

@json_response
@login_required
def market_test_vote(request):
    bill = get_object_or_404(Bill, id = request.POST.get("bill", "0"))
    prediction = int(request.POST.get("prediction", "0"))
    
    from website.models import TestMarketVote
    if prediction != 0:
        v, is_new = TestMarketVote.objects.get_or_create(user=request.user, bill=bill,
            defaults = { "prediction": prediction })
        if not is_new:
            v.prediction = prediction
            v.save()
    else:
        TestMarketVote.objects.filter(user=request.user, bill=bill).delete()
    return { "vote": prediction }

@render_to('bill/bill_text.html')
def bill_text(request, congress, type_slug, number):
    # if type_slug.isdigit():
        # bill_type = type_slug
    # else:
        # try:
            # bill_type = BillType.by_slug(type_slug)
        # except BillType.NotFound:
            # raise Http404("Invalid bill type: " + type_slug)
    # bill = get_object_or_404(Bill, congress=congress, bill_type=bill_type, number=number)
    # 
    # pv_bill_id = None
    # bill_text_content = None
    # 
    # if bill.congress == CURRENT_CONGRESS:
        # # the congress number filter doesn't seem to work
        # pvinfo = query_popvox("v1/bills/search", {
                # "q": bill.display_number + "/" + str(bill.congress)
            # })
        # try:
            # pv_bill_id = pvinfo["items"][0]["id"]
        # except:
            # pass
    # else:
    
    try:
        bill_type = BillType.by_slug(type_slug)
    except BillType.NotFound:
        raise Http404("Invalid bill type: " + type_slug)
    bill = get_object_or_404(Bill, congress=congress, bill_type=bill_type, number=number)
    
    try:
        bt = BillType.by_value(bill.bill_type).xml_code
        bill_text_content = open("data/us/bills.text/%s/%s/%s%d.html" % (bill.congress, bt, bt, bill.number)).read()
        
        mods = lxml.etree.parse("data/us/bills.text/%s/%s/%s%d.mods.xml" % (bill.congress, bt, bt, bill.number))
        ns = { "mods": "http://www.loc.gov/mods/v3" }
        docdate = mods.xpath("string(mods:originInfo/mods:dateIssued)", namespaces=ns)
        gpo_url = mods.xpath("string(mods:identifier[@type='uri'])", namespaces=ns)
        gpo_pdf_url = mods.xpath("string(mods:location/url[@displayLabel='PDF rendition'])", namespaces=ns)
        doc_version = mods.xpath("string(mods:extension/mods:billVersion)", namespaces=ns)
        
        docdate = datetime.date(*(int(d) for d in docdate.split("-")))
        
        from billtext import bill_gpo_status_codes
        doc_version_name = bill_gpo_status_codes[doc_version]
    except IOError:
        bill_text_content = None
        
    return {
        'bill': bill,
        "congressdates": get_congress_dates(bill.congress),
        #"pv_bill_id": pv_bill_id,
        "text_html": bill_text_content,
        "docdate": docdate,
        "gpo_url": gpo_url,
        "gpo_pdf_url": gpo_pdf_url,
        "doc_version": doc_version,
        "doc_version_name": doc_version_name,
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
            ("Active Bills", "bills", " that are awaiting the president's signature, have differences between the chambers to be resolved, or were vetoed", BillStatus.active_status),
            ("Waiting Bills", "bills and resolutions", " that had a significant vote", BillStatus.waiting_status),
            ("Successful Bills", "enacted bills", "", BillStatus.final_status_passed_bill),
            ("Successful Resolutions", "passed resolutions", "", BillStatus.final_status_passed_resolution),
            ("Unsuccessful Bills", "bills and resolutions", " that failed a vote", BillStatus.final_status_failed),
            ("Inactive Bills", "bills and resolutions", " that have been introduced, referred to committee, or reported by committee", BillStatus.inactive_status),
        ]
        
        dhg_cutoff = datetime.datetime.now() - datetime.timedelta(days=10)
        def loadgroupqs(statuses):
            qs = Bill.objects.filter(congress=CURRENT_CONGRESS, current_status__in=statuses)
            return qs.filter(docs_house_gov_postdate=None) | qs.exclude(docs_house_gov_postdate__gt=dhg_cutoff)
        
        groups = [
            (   g[0], # title
                g[1], # text 1
                g[2], # text 2
                "/congress/bills/browse?status=" + ",".join(str(s) for s in g[3]), # link
               loadgroupqs(g[3]).count(), # count in category
               loadgroupqs(g[3]).order_by('-current_status_date')[0:6], # top 6 in this category
                )
            for g in groups ]
            
        dhg_bills = Bill.objects.filter(congress=CURRENT_CONGRESS, docs_house_gov_postdate__gt=dhg_cutoff)
        if len(dhg_bills) > 0:
            groups.insert(0, (
                "Coming Up",
                "bills and resolutions",
                " that the House Majority Leader has indicated may be considered in the week ahead",
                "http://docs.house.gov",
                len(dhg_bills),
                dhg_bills.order_by('-docs_house_gov_postdate')
            ))
        
        start, end = get_congress_dates(CURRENT_CONGRESS)
        end_year = end.year if end.month > 1 else end.year-1 # count January finishes as the prev year
        current_congress = '%s Congress, for %d-%d' % (ordinal(CURRENT_CONGRESS), start.year, end.year)    
        
        return {
            "total": Bill.objects.filter(congress=CURRENT_CONGRESS).count(),
            "current_congress": current_congress,
            "groups": groups,
            "subjects": subject_choices(),
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
    

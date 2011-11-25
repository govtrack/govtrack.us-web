# -*- coding: utf-8 -*-
from django.shortcuts import redirect, get_object_or_404
from django.core.urlresolvers import reverse
from django.http import Http404
from django.conf import settings

from common.decorators import render_to
from common.pagination import paginate

from bill.models import Bill, BillType
from bill.search import bill_search_manager
from bill.title import get_secondary_bill_title

from settings import CURRENT_CONGRESS

from us import get_congress_dates

import urllib, urllib2, json

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
    return {
        'bill': bill,
        "congressdates": get_congress_dates(bill.congress),
        "subtitle": get_secondary_bill_title(bill, bill.titles),
    }

@render_to('bill/bill_text.html')
def bill_text(request, congress, type_slug, number):
    if type_slug.isdigit():
        bill_type = type_slug
    else:
        try:
            bill_type = BillType.by_slug(type_slug)
        except BillType.NotFound:
            raise Http404("Invalid bill type: " + type_slug)
    bill = get_object_or_404(Bill, congress=congress, bill_type=bill_type, number=number)
    
    pv_bill_id = None
    pvinfo = query_popvox("v1/bills/search", {
            "q": bill.display_number()
        })
    try:
        pv_bill_id = pvinfo["items"][0]["id"]
    except:
        pass
    
    return {
        'bill': bill,
        "congressdates": get_congress_dates(bill.congress),
        "pv_bill_id": pv_bill_id,
    }

@render_to('bill/bill_list.html')
def bill_list(request):
    return bill_search_manager().view(request, "bill/bill_list.html", defaults={"congress": CURRENT_CONGRESS})

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


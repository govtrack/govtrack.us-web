# -*- coding: utf-8 -*-
from django.shortcuts import redirect, get_object_or_404
from django.core.urlresolvers import reverse
from django.http import Http404

from common.decorators import render_to
from common.pagination import paginate

from bill.models import Bill, BillType
from bill.search import bill_search_manager
from bill.title import get_secondary_bill_title

from settings import CURRENT_CONGRESS

from us import get_congress_dates

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


@render_to('bill/bill_list.html')
def bill_list(request):
    return bill_search_manager().view(request, "bill/bill_list.html", defaults={"congress": CURRENT_CONGRESS})


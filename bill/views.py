# -*- coding: utf-8 -*-
from django.shortcuts import redirect, get_object_or_404
from django.core.urlresolvers import reverse
from django.http import Http404

from common.decorators import render_to
from common.pagination import paginate

from bill.models import Bill, BillType
from bill.search import bill_search_manager

@render_to('bill/bill_details.html')
def bill_details(request, congress, type_slug, number):
    if type_slug.isdigit():
        bill_type = type_slug
    else:
        try:
            bill_type = BillType.by_slug(type_slug)
        except BillType.NotFound:
            raise Http404
    bill = get_object_or_404(Bill, congress=congress, bill_type=bill_type, number=number)
    return {'bill': bill,}


@render_to('bill/bill_list.html')
def bill_list(request):
	return bill_search_manager().view(request, "bill/bill_list.html")


# -*- coding: utf-8 -*-
from django.shortcuts import redirect, get_object_or_404
from django.core.urlresolvers import reverse
from django.http import Http404

from common.decorators import render_to
from common.pagination import paginate

from bill.models import Bill, BillType
from bill.search import bill_search_manager
from smartsearch.manager import SearchManager

@render_to('bill/bill_details.html')
def bill_details(request, congress, type_slug, number):
    try:
        bill_type = BillType.by_slug(type_slug)
    except BillType.NotFound:
        raise Http404
    bill = get_object_or_404(Bill, congress=congress, bill_type=bill_type,
                             number=number)
    return {'bill': bill,
            }


@render_to('bill/bill_list.html')
def bill_list(request):
    sm = bill_search_manager()
    if 'congress' in request.GET:
        form = sm.form(request)
    else:
        form = sm.form()
    qs = form.queryset()
    page = paginate(qs, request, per_page=50)
    return {'page': page,
            'form': form,
            }

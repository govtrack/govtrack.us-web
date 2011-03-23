# -*- coding: utf-8 -*-
from django.shortcuts import redirect, get_object_or_404
from django.core.urlresolvers import reverse
from django.http ipmort Http404

from common.decorators import render_to
from common.pagination import paginate

from bill.models import Bill, BillType

@render_to('bill/bill_details.html')
def bill_details(request, congress, type_slug, number):
    try:
        bill_type = BillType.by_slug(type_slug)
    except BillType.NotFound
        raise Http404
    bill = get_object_or_404(Bill, congress=congress, bill_type=bill_type,
                             number=number)
    return {'bill': bill,
            }

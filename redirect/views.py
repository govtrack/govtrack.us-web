# -*- coding: utf-8 -*-
import re

from django.shortcuts import redirect, get_object_or_404
from django.core.urlresolvers import reverse
from django.http import Http404

from common.decorators import render_to
from common.pagination import paginate

from person.models import Person
from committee.models import Committee
from bill.models import Bill, BillType

BILL_TOKEN_REGEXP = re.compile('^([a-z]+)(\d+)-(\d+)$')

def person_redirect(request):
    pk = request.GET.get('id', None)
    person = get_object_or_404(Person, pk=pk)
    return redirect(person, permanent=True)


def committee_redirect(request):
    pk = request.GET.get('id', None)
    if len(pk) > 4:
        parent_pk = pk[:4]
        child_pk = pk[4:]
        committee = get_object_or_404(Committee, code=child_pk, committee__code=parent_pk)
    else:
        committee = get_object_or_404(Committee, code=pk)
    return redirect(committee, permanent=True)


def bill_redirect(request):
    """
    Redirect requests to obsolete bill urls which look like:

        /congress/bill.xpd?bill=[type_code][congress_number]-[bill_num]
    """

    token = request.GET.get('bill', '')
    match = BILL_TOKEN_REGEXP.search(token)
    if not match:
        raise Http404()
    type_code, congress, number = match.groups()
    try:
        bill_type = BillType.by_xml_code(type_code)
    except BillType.NotFound:
        raise Http404()
    bill = get_object_or_404(Bill, bill_type=bill_type, congress=congress,
                             number=number)
    return redirect(bill, permanent=True)

# -*- coding: utf-8 -*-
import re

from django.shortcuts import redirect, get_object_or_404
from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponseRedirect

from common.decorators import render_to
from common.pagination import paginate

from person.models import Person
from committee.models import Committee
from bill.models import Bill, BillType, BillTerm, TermType

BILL_TOKEN_REGEXP = re.compile('^([a-z]+)(\d+)-(\d+)$')

def person_redirect(request):
    try:
        pk = int(request.GET.get('id', ""))
    except ValueError:
        raise Http404()
    person = get_object_or_404(Person, pk=pk)
    return redirect(person, permanent=True)

def district_maps_redirect(request):
    url = "/congress/members"
    if "state" in request.GET: url += "/" + request.GET["state"]
    if "district" in request.GET: url += "/" + request.GET["district"]
    return HttpResponseRedirect(url)
    
def committee_redirect(request):
    pk = request.GET.get('id', None)
    if pk == None:
        return redirect("/congress/committees", permanent=True)
    committee = get_object_or_404(Committee, code=pk)
    return redirect(committee, permanent=True)


def bill_redirect(request, istext=None):
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
    return redirect(bill.get_absolute_url() + ("" if not istext else "/text"), permanent=True)

def bill_search_redirect(request):
    qs = request.META.get("QUERY_STRING", "")
    if len(qs) > 0: qs = "?" + qs
    return HttpResponseRedirect("/congress/bills/browse" + qs)

def bill_overview_redirect(request):
    return HttpResponseRedirect("/congress/bills")

def subject_redirect(request):
    if request.GET.get("type", "") != "crs" or "term" not in request.GET:
        return redirect("/congress/bills", permanent=True)
    try:
        term = get_object_or_404(BillTerm, name=request.GET["term"], term_type=TermType.new)
    except:
        term = get_object_or_404(BillTerm, name=request.GET["term"], term_type=TermType.old)
    return redirect(term.get_absolute_url(), permanent=True)

def vote_redirect(request):
    if not "-" in request.GET.get("vote", ""):
        return HttpResponseRedirect("/congress/votes")
    try:
        a, roll = request.GET["vote"].split("-")
    except:
        raise Http404()
    chamber = a[0]
    session = a[1:]
    from us import get_all_sessions
    for cong, sess, start, end in get_all_sessions():
        if sess == session or str(cong) + "_" + sess == session:
            return HttpResponseRedirect("/congress/votes/%s-%s/%s%s" % (cong, sess, chamber, roll))
    raise Http404()
    
def votes_redirect(request):
    return HttpResponseRedirect("/congress/votes") # missing year, chamber, person parameters


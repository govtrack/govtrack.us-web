# -*- coding: utf-8 -*-
from django.shortcuts import redirect, get_object_or_404
from django.core.urlresolvers import reverse
from django.http import Http404
from django.conf import settings
from django.contrib.humanize.templatetags.humanize import ordinal

from common.decorators import render_to
from common.pagination import paginate

from bill.models import Bill, BillType, BillStatus, BillTerm, TermType
from bill.search import bill_search_manager
from bill.title import get_secondary_bill_title
from committee.models import CommitteeMember, CommitteeMemberRole
from committee.util import sort_members
from person.models import Person
from events.models import Feed

from settings import CURRENT_CONGRESS

from us import get_congress_dates

import urllib, urllib2, json, os.path

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
    
    relevant_assignments = []
    good_cosp_assignments = 0
    good_cosp_assignments_other = False
    if bill.congress == CURRENT_CONGRESS:
        for ca in sort_members(bill.sponsor.committeeassignments.filter(committee__in=bill.committees.all()).select_related()):
            relevant_assignments.append( ("The sponsor", ca) )
            break
        for ca in sort_members(CommitteeMember.objects.filter(person__in=bill.cosponsors.all(), committee__in=bill.committees.all()).select_related()):
            if ca.role not in (CommitteeMemberRole.member, CommitteeMemberRole.exofficio):
                relevant_assignments.append( (ca.person.name + ", a cosponsor,", ca) )
                good_cosp_assignments_other = True
            else:
                good_cosp_assignments += 1
        
    summary = None
    sfn = "data/us/%d/bills.summary/%s%d.summary.xml" % (bill.congress, BillType.by_value(bill.bill_type).xml_code, bill.number)
    if os.path.exists(sfn):
        from lxml import etree
        dom = etree.parse(open(sfn))
        xslt_root = etree.XML('''
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
        <xsl:output omit-xml-declaration="yes"/>
        <xsl:template match="summary//Paragraph[string(.)!='']">
            <div style="margin-top: .5em; margin-bottom: .5em">
                <xsl:apply-templates/>
            </div>
        </xsl:template>

        <xsl:template match="Division|Title|Subtitle|Part|Chapter|Section">
            <xsl:if test="not(@number='meta')">
            <div>
                <xsl:choose>
                <xsl:when test="@name='' and count(*)=1">
                <div style="margin-top: .75em">
                <span xml:space="preserve" style="font-weight: bold;"><xsl:value-of select="name()"/> <xsl:value-of select="@number"/>.</span>
                <xsl:value-of select="Paragraph"/>
                </div>
                </xsl:when>

                <xsl:otherwise>
                <div style="font-weight: bold; margin-top: .75em" xml:space="preserve">
                    <xsl:value-of select="name()"/>
                    <xsl:value-of select="@number"/>
                    <xsl:if test="not(@name='')"> - </xsl:if>
                    <xsl:value-of select="@name"/>
                </div>
                <div style="margin-left: 2em">
                    <xsl:apply-templates/>
                </div>
                </xsl:otherwise>
                </xsl:choose>
            </div>
            </xsl:if>
        </xsl:template>
</xsl:stylesheet>''')
        transform = etree.XSLT(xslt_root)
        summary = transform(dom)
        if unicode(summary).strip() == "":
            summary = None
    
    return {
        'bill': bill,
        "congressdates": get_congress_dates(bill.congress),
        "subtitle": get_secondary_bill_title(bill, bill.titles),
        "summary": summary,
        "relevant_assignments": relevant_assignments,
        "good_cosp_assignments": good_cosp_assignments,
        "good_cosp_assignments_other": good_cosp_assignments_other,
        "current": bill.congress == CURRENT_CONGRESS,
        "dead": bill.congress != CURRENT_CONGRESS and bill.current_status not in BillStatus.final_status_obvious,
        'feed': Feed.BillFeed(bill),
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
            "q": bill.display_number
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

def bill_list(request):
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
    groups = [
        ("Active Bills", "bills", " that are awaiting the president's signature, have differences between the chambers to be resolved, or were vetoed", BillStatus.active_status),
        ("Waiting Bills", "bills and resolutions", " that had a significant vote", BillStatus.waiting_status),
        ("Successful Bills", "enacted bills", "", BillStatus.final_status_passed_bill),
        ("Successful Resolutions", "passed resolutions", "", BillStatus.final_status_passed_resolution),
        ("Unsuccessful Bills", "bills and resolutions", " that failed a vote", BillStatus.final_status_failed),
        ("Inactive Bills", "bills and resolutions", " that have been introduced, referred to committee, or reported by committee", BillStatus.inactive_status),
    ]
    
    groups = [
        (g[0], g[1], g[2], ",".join(str(s) for s in g[3]), Bill.objects.filter(congress=CURRENT_CONGRESS, current_status__in=g[3]).order_by('-current_status_date'))
        for g in groups ]
    
    start, end = get_congress_dates(CURRENT_CONGRESS)
    end_year = end.year if end.month > 1 else end.year-1 # count January finishes as the prev year
    current_congress = '%s Congress, for %d-%d' % (ordinal(CURRENT_CONGRESS), start.year, end.year)    
    
    return {
        "total": Bill.objects.filter(congress=CURRENT_CONGRESS).count(),
        "current_congress": current_congress,
        "groups": groups,
        "subjects": subject_choices(),
    }

def subject(request, sluggedname, termid):
    ix = BillTerm.objects.get(id=termid)
    if ix.parents.all().count() == 0:
        ix1 = ix
        ix2 = None
    else:
        ix1 = ix.parents.all()[0]
        ix2 = ix
    return show_bill_browse("bill/subject.html", request, ix1, ix2, { "term": ix, "feed": Feed.IssueFeed(ix) })
    

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
from committee.models import CommitteeMember, CommitteeMemberRole
from committee.util import sort_members

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
	for ca in sort_members(bill.sponsor.committeeassignments.filter(committee__in=bill.committees.all()).select_related()):
		relevant_assignments.append( ("The sponsor", ca) )
		break
	good_cosp_assignments = 0
	good_cosp_assignments_other = False
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

@render_to('bill/bill_list.html')
def bill_list(request):
    return bill_search_manager().view(request, "bill/bill_list.html",
    	defaults={
    		"congress": CURRENT_CONGRESS,
    		"sponsor": request.GET.get("sponsor", None),
    		"terms": request.GET.get("subject", None),
    	},
    	noun = ("bill", "bills")
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


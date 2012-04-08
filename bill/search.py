from django import forms
from django.contrib.humanize.templatetags.humanize import ordinal

from smartsearch.manager import SearchManager

from bill.models import Bill, BillTerm, TermType, BillType, BillStatus
from person.models import Person
from person.util import load_roles_at_date
from us import get_congress_dates
from settings import CURRENT_CONGRESS

import re

subject_choices_data = None
def subject_choices(include_legacy=True):
    global subject_choices_data
    if subject_choices_data == None:
        top_terms = { }
        for t in BillTerm.objects.exclude(parents__id__gt=0):
            x = []
            top_terms[ (-t.term_type, t.name, t.id) ] = x
            for tt in t.subterms.all():
                x.append((tt.id, "-- " + tt.name))
                
        ret0 = [] # all terms
        ret1 = [] # current terms only
        for t, subterms in sorted(top_terms.items(), key = lambda kv : kv[0]):
            for ret in ret0, ret1:
                if -t[0] == TermType.old and ret == ret1: continue
                ret.append((t[2], t[1] + ("" if -t[0] == TermType.new else " (Legacy Subject Code)")))
                for tt in sorted(subterms, key = lambda kv : kv[1]):
                    ret.append(tt)
        
        subject_choices_data = (ret0, ret1)
    
    return subject_choices_data[0 if include_legacy else 1]

def get_terms(terms):
    return sorted([(t.id, t.name + ("" if t.term_type==TermType.new else " (Legacy Subject)")) for t in terms], key = lambda x : ("Legacy Subject" in x[1], x[1]))

def sub_terms(request):
    if "terms" in request.POST:
        return get_terms(BillTerm.objects.filter(parents__id=request.POST["terms"]))
    else:
        return []
def sub_term_filter(qs, form):
    if form.get("terms2", "") not in ("", "__ALL__"):
        # overwrite the terms filter set by the main form field
        return {"terms__in": [form["terms2"]]}
    return None

def format_congress_number(value):
    start, end = get_congress_dates(value)
    end_year = end.year if end.month > 1 else end.year-1 # count January finishes as the prev year
    return '%s Congress: %d-%d' % (ordinal(value), start.year, end.year)

# this regex must match slugs in BillType enum!
bill_number_re = re.compile(r"(hr|s|hconres|sconres|hjres|sjres|hres|sres)(\d+)(/(\d+))?", re.I)
def parse_bill_number(q, congress=None):
    m = bill_number_re.match(q.replace(" ", "").replace(".", "").replace("-", ""))
    if m == None: return None
    if m.group(3) != None:
        cn = int(m.group(4))
    elif congress != None:
        try:
            cn = int(congress)
        except:
            cn = CURRENT_CONGRESS
    else:
        cn = CURRENT_CONGRESS
    try:
        return Bill.objects.get(congress=cn, bill_type=BillType.by_slug(m.group(1).lower()), number=int(m.group(2)))
    except Bill.DoesNotExist:
        return None

def bill_search_manager():
    sm = SearchManager(Bill)
    sm.add_option('text', label='search title', type="text", choices="NONE")
    sm.add_option('congress', type="select", formatter=format_congress_number, sort="KEY-REVERSE")
    sm.add_option('sponsor', type="select", sort="LABEL", formatter=lambda p : p.sortname)
    sm.add_option('current_status', label="current status", sort='LABEL')
    sm.add_option('terms', type="select", label="subject", choices=get_terms(BillTerm.objects.exclude(parents__id__gt=0)))
    sm.add_option('terms2', type="select", label="subject 2", choices=sub_terms, visible_if=lambda post:"terms" in post, filter=sub_term_filter)
    sm.add_option('bill_type', label="bill or resolution type")
    
    #sm.add_sort("Popularity", "-total_bets", default=True)
    sm.add_sort("Introduced Date (Newest First)", "-introduced_date")
    sm.add_sort("Introduced Date (Oldest First)", "introduced_date")
    sm.add_sort("Last Major Action (Recent First)", "-current_status_date", default=True)

    def safe_strftime(date, format):
        return date.replace(year=3456).strftime(format).replace("3456", str(date.year)).replace(" 12:00AM", "")
    
    sm.add_bottom_column(lambda bill, form :
            "Sponsor: " + unicode(bill.sponsor) + "\n" +
            "Introduced: " + safe_strftime(bill.introduced_date, "%b %d, %Y") + "\n" +
            ((bill.get_current_status_display() + ": " + safe_strftime(bill.current_status_date, "%b %d, %Y")) if bill.current_status != BillStatus.introduced else ""))
    
    return sm

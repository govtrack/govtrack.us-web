from django import forms
from django.contrib.humanize.templatetags.humanize import ordinal

from smartsearch.manager import SearchManager

from bill.models import Bill, BillTerm, TermType, BillType, BillStatus, USCSection
from person.models import Person
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

def sub_terms(requestargs):
    if "terms" in requestargs:
        return get_terms(BillTerm.objects.filter(parents__id=requestargs["terms"]))
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
bill_number_re = re.compile(r"(hr|s|hconres|sconres|hjres|sjres|hres|sres)(\d+)(/(\d+))?$", re.I)
slip_law_number_re = re.compile(r"(P(?:ub[a-z]*)?|P[rv][a-z]*)L(?:aw)?(\d+)-(\d+)$", re.I)

def parse_bill_citation(q, congress=None):
    b = parse_bill_number(q, congress=congress)
    if not b: b = parse_slip_law_number(q)
    return b
    
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

def parse_slip_law_number(q):
    m = slip_law_number_re.match(q.replace(" ", "").replace(".", "").replace(u"\u2013", "-"))
    if m == None: return None
    pub_priv, cn, ln = m.groups()
    try:
        return Bill.objects.get(
            congress = int(cn),
            sliplawpubpriv = "PUB" if (pub_priv.upper() == "P" or pub_priv.upper().startswith("PUB")) else "PRI",
            sliplawnum = int(ln)
            )
    except Bill.DoesNotExist:
        return None

def similar_to(qs, form):
	if form.get("similar_to", "").strip() != "":
		b = parse_bill_number(form["similar_to"])
		if b:
			return qs.more_like_this(b)
	return None

def usc_cite(qs, form):
	# If the value isn't an integer, map the citation string to an ID.
	v = form.get("usc_cite", "").strip()
	if v != "":
		if not re.match("^\d+$", v):
			v = USCSection.objects.get(citation=v).id
		return qs.filter(usc_citations_uptree=v)
	return None

def bill_search_manager():
    sm = SearchManager(Bill, connection="bill")
    
    sm.add_option('similar_to', type="text", label="similar to (enter bill number)", visible_if=lambda form : False, filter=similar_to)
    sm.add_option('usc_cite', type="text", label="cites", visible_if=lambda form : False, orm_field_name='usc_citations_uptree', filter=usc_cite)
    
    sm.add_option('text', label='search title & full text', type="text", choices="NONE")
    sm.add_option('congress', type="select", formatter=format_congress_number, sort="KEY-REVERSE")
    sm.add_option('sponsor', type="select", sort="LABEL", formatter=lambda p : p.sortname)
    sm.add_option('current_status', label="current status", sort=lambda s : BillStatus.by_value(s).sort_order)
    sm.add_option('enacted_ex', type="boolean", label=u"Enacted \u2014 Including by Incorporation into Other Bills")
    sm.add_option('cosponsors', label="cosponsor", type="select", sort="LABEL", formatter=lambda p : p.sortname)
    sm.add_option('committees', label="committee", type="select", sort="LABEL", formatter=lambda c : c.shortname)
    sm.add_option('terms', type="select", label="subject", choices=get_terms(BillTerm.objects.exclude(parents__id__gt=0)))
    sm.add_option('terms2', type="select", label="subject 2", choices=sub_terms, visible_if=lambda post:"terms" in post, filter=sub_term_filter)
    sm.add_option('sponsor_party', label="party of sponsor", type="select")
    sm.add_option('bill_type', label="bill or resolution type")
    
    #sm.add_sort("Popularity", "-total_bets", default=True)
    # default sort order is handled by the view
    sm.add_sort("Secret Sauce", "-proscore")
    sm.add_sort("Introduced Date (Newest First)", "-introduced_date")
    sm.add_sort("Introduced Date (Oldest First)", "introduced_date")
    sm.add_sort("Last Major Action (Recent First)", "-current_status_date")

    #def safe_strftime(date, format):
    #    return date.replace(year=3456).strftime(format).replace("3456", str(date.year)).replace(" 12:00AM", "")
    
    sm.set_template("""
	<div class="row">
		<div class="col-xs-2 col-md-1" style="padding-right: 0">
			<img src="{{object.get_absolute_url}}/thumbnail?aspect=1.2&width=125" class="img-responsive"/>
		</div>
		<div class="col-xs-10 col-md-11">
    	<div style="margin-bottom: 3px"><a href="{{object.get_absolute_url}}" style="font-size: 15px; line-height: 125%;">{{object|truncatewords_html:50}}</a></div>
		<div style="font-size: 90%">
    	{% if object.sponsor %}<div style="margin-bottom: 3px">Sponsor: {{object.sponsor}}</div>{% endif %}
		<table width="100%"><tr valign="top">
    	{% if object.source != "statutesatlarge" %}<td width="25%" style="padding-right: 1.5em">Introduced<br>{{object.introduced_date}}</td>{% else %}<td/>{% endif %}
    	{% if object.source != "americanmemory" and object.get_current_status_display_simple != "Introduced" %}<td width="50%" style="padding-right: 1.5em">{% if object.source != "statutesatlarge" %}{{object.get_current_status_display_simple}}{% else %}Enacted/Agreed to{% endif %}<br>{{object.current_status_date}}</td>{% else %}<td/>{% endif %}
		{% if object.is_alive and object.get_prognosis %}<td width="25%" style="padding-right: 1.5em">Prognosis<br>{{object.get_prognosis.prediction|floatformat:0}}%</td>{% else %}<td/>{% endif %}
		</tr></table>
        {% with b_list=object.was_enacted_ex %}
        {% for b in b_list %}
            {% if b and b != object %}
                <div>Enacted via <a href="{{b.get_absolute_url}}" style="text-decoration: none">{{b.title}}</a></div>
            {% endif %}
        {% endfor %}
		</div>
		</div>
	</div>
        {% endwith %}
	""")
    
    return sm

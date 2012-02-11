from django import forms
from django.contrib.humanize.templatetags.humanize import ordinal

from smartsearch.manager import SearchManager

from bill.models import Bill, BillTerm, TermType
from person.models import Person
from person.util import load_roles_at_date

def congress_list():
    end_year = 2012
    end_congress = 112
    for x in xrange(112, 93-1, -1):
        end = end_year - (end_congress - x) * 2
        start = end - 1
        yield (x, '%s Congress (%d-%d)' % (ordinal(x), start, end))

subject_choices_data = None
def subject_choices(include_legacy=True):
    global subject_choices_data
    if subject_choices_data == None:
        top_terms = { }
        for t in BillTerm.objects.filter(subterms__id__gt=0).distinct():
            top_terms[ (-t.term_type, t.name, t.id) ] = [ ]
        for t in BillTerm.objects.filter(parents__id__gt=0).distinct():
            for p in t.parents.all():
                top_terms[ (-p.term_type, p.name, p.id) ].append((t.id, "-- " + t.name))
                
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

def person_list():
    persons = Person.objects.all()
    load_roles_at_date(persons) 
    return [('', 'Any')] + [(x.pk, unicode(x)) for x in persons]

def congress_filter(qs, form):
    c = form['congress']
    if c.strip() != '':
        qs = qs.filter(congress=c)
    return qs

def name_filter(qs, form):
    name = form["title"]
    if name.strip() != "":
        qs = qs.filter(title__contains=name.strip())
    return qs

def bill_search_manager():
    sm = SearchManager(Bill)
    sm.add_option('title', label='search title', type="text", filter=name_filter, choices="NONE")
    sm.add_option('congress', type="select", filter=congress_filter, choices=congress_list())
    sm.add_option('sponsor', type="select")
    sm.add_option('current_status', label="current status")
    sm.add_option('terms', type="select", label="subject", choices=subject_choices())
    sm.add_option('bill_type', label="bill or resolution type")
    sm.add_bottom_column(lambda bill, form : "Sponsor: " + unicode(bill.sponsor))
    return sm

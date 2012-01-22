from django import forms
from django.contrib.humanize.templatetags.humanize import ordinal

from smartsearch.manager import SearchManager

from bill.models import Bill
from person.models import Person
from person.util import load_roles_at_date

def congress_list():
    end_year = 2012
    end_congress = 112
    for x in xrange(112, 93-1, -1):
        end = end_year - (end_congress - x) * 2
        start = end - 1
        yield (x, '%s Congress (%d-%d)' % (ordinal(x), start, end))

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
    sm.add_option('bill_type')
    sm.add_option('current_status')
    sm.add_bottom_column(lambda bill, form : "Sponsor: " + unicode(bill.sponsor))
    return sm

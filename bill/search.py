from django import forms
from django.contrib.humanize.templatetags.humanize import ordinal

from smartsearch.manager import SearchManager

from bill.models import Bill
from person.models import Person
from person.util import load_roles_at_date

def congress_list():
    yield ('', 'Any')
    end_year = 2012
    end_congress = 112
    for x in xrange(112, 102, -1):
        end = end_year - (end_congress - x) * 2
        start = end - 1
        yield (x, '%s Congress (%d-%d)' % (ordinal(x), start, end))

def person_list():
    persons = Person.objects.all()
    load_roles_at_date(persons) 
    return [('', 'Any')] + [(x.pk, unicode(x)) for x in persons]

def cosponsor_filter(qs, form):
    pk = form.cleaned_data['cosponsor']
    if pk != '':
        qs = qs.filter(cosponsors__pk=pk)
    return qs


year_field = forms.ChoiceField(choices=congress_list(), required=False)
cosponsor_field = forms.ChoiceField(choices=person_list(), required=False)

def year_filter(qs, form):
    year = form.cleaned_data['congress']
    if year != '':
        qs = qs.filter(congress=year)
    return qs

def bill_search_manager():
    sm = SearchManager(Bill)
    sm.add_option('congress', field=year_field, filter=year_filter)
    sm.add_option('sponsor', simple=True)
    sm.add_option('cosponsor', field=cosponsor_field, filter=cosponsor_filter)
    sm.add_option('current_status')
    return sm

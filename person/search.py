from django import forms

from smartsearch.manager import SearchManager

from person.models import Person

years = [('', 'Any')] + [(x, str(x)) for x in xrange(2011, 1788, -1)]
year_field = forms.ChoiceField(choices=years, required=False)

def year_filter(qs, form):
    year = form.cleaned_data['year']
    if year != '':
        qs = qs.filter(created__year=year)
    return qs

def person_search_manager():
    sm = SearchManager(Person)
    #sm.add_option('year', field=year_field, filter=year_filter)
    #sm.add_option('chamber')
    #sm.add_option('category')
    return sm

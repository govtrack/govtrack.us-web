from django import forms

from smartsearch.manager import SearchManager

from person.models import Person, PersonRole

years = [('', 'Any')] + [(x, str(x)) for x in xrange(2011, 1788, -1)]
year_field = forms.ChoiceField(choices=years, required=False)

def year_filter(qs, form):
    year = form.cleaned_data['year']
    if year != '':
        qs = qs.filter(created__year=year)
    return qs

def person_search_manager():
    sm = SearchManager(Person)
    sm.add_option('roles__current', label="currently serving?")
    sm.add_option('roles__role_type', label="type")
    sm.add_option('roles__state', sort=False, widget=forms.Select)
    sm.add_option('roles__district', sort=False, choices=[('_ALL_', 'Any'), ('0', 'At Large')] + [(x, str(x)) for x in xrange(1, 53+1)], widget=forms.Select)
    sm.add_option('roles__party', widget=forms.Select)
    sm.add_option('gender')
    return sm

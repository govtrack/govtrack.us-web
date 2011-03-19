from django import forms

from smartsearch.manager import SearchManager

from vote.models import Vote, CongressChamber, VoteCategory

years = [('', 'Any')] + [(x, str(x)) for x in xrange(2011, 1788, -1)]
year_field = forms.ChoiceField(choices=years, required=False)

def year_filter(qs, form):
    year = form.cleaned_data['year']
    if year != '':
        qs = qs.filter(created__year=year)
    return qs

def vote_search_manager():
    sm = SearchManager(Vote)
    sm.add_option('year', field=year_field, filter=year_filter)
    sm.add_option('chamber')
    sm.add_option('category')
    return sm

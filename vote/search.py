from datetime import datetime

from django import forms

from smartsearch.manager import SearchManager

from vote.models import Vote, CongressChamber, VoteCategory

years = [("_ALL_", "All")] + [(x, str(x)) for x in xrange(datetime.now().year, 1788, -1)]

def year_filter(qs, form):
    year = form['year']
    if year != []:
        qs = qs.filter(created__year=year[0])
    return qs
    
def sort_filter(qs, form):
    sort = form['sort']
    if sort != []:
        if sort[0] == "date":
            qs = qs.extra(order_by=["-created"])
        if sort[0] == "spread":
            qs = qs.extra(order_by=["total_plus-total_minus"])
    return qs

def vote_search_manager():
    sm = SearchManager(Vote, qs=Vote.objects.order_by('-created'))
    
    #sm.add_option('sort', filter=sort_filter, widget=forms.Select, choices=[("date", "Date"), ("spread", "Spread")])
    #sm.add_option('year', filter=year_filter, widget=forms.Select, choices=years)
    sm.add_option('chamber')
    sm.add_option('category')
    
    def truncate(name):
        if len(name) < 60: return name
        return name[0:57] + "..."
    
    sm.add_left_column("Vote and Date", lambda vote, form : vote.name() + "\n" + vote.created.strftime("%b %d, %Y %I:%M%p"))
    sm.add_bottom_column(lambda vote, form : vote.summary())
    sm.add_column("Description and Result", lambda vote, form : truncate(vote.question))
    
    return sm

from datetime import datetime

from django import forms
from django.contrib.humanize.templatetags.humanize import ordinal
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

from smartsearch.manager import SearchManager

from vote.models import Vote, CongressChamber, VoteCategory
from us import get_all_sessions

def sort_filter(qs, form):
    sort = form['sort']
    if sort != []:
        if sort[0] == "date":
            qs = qs.extra(order_by=["-created"])
        if sort[0] == "spread":
            qs = qs.extra(order_by=["total_plus-total_minus"])
    return qs

def session_filter(qs, form):
	session_index = form["session"]
	if session_index != None:
		s = get_all_sessions()[int(session_index)]
		qs = qs.filter(congress=s[0], session=s[1])
	return qs
	
def vote_search_manager():
    sm = SearchManager(Vote, qs=Vote.objects.order_by('-created'))
    
    # show sessions as year+session for non-year-based sessions,
    # and then just the session number (the year) for year-based
    # sessions.
    def format_session(s):
    	if s[0] >= 77:
    		 # year and congress number in parens
    		return s[1] + " (" + ordinal(s[0]) + " Congress)"
    	else:
    		# date range and congress number in parens
    		if s[2].year == s[3].year:
				# strftime requires year>=1900, so fool it for generating
				# month names by replacing old years with 1900
				if s[2].month == s[3].month:
					return str(s[2].year) + " " + s[2].replace(1900).strftime("%b") + " (" + ordinal(s[0]) + " Congress)"
				else:
					return str(s[2].year) + " " + s[2].replace(1900).strftime("%b-") + s[3].replace(1900).strftime("%b") + " (" + ordinal(s[0]) + " Congress)"
    		else:
    			return str(s[2].year) + "-" + str(s[3].year) + " (" + ordinal(s[0]) + " Congress)"
    	
    session_choices = reversed([(i, format_session(cs)) for (i,cs) in enumerate(get_all_sessions())])
    
    sm.add_option('session', type="select", choices=session_choices, filter=session_filter, help="Note: Even-year sessions extend a few days into the next year.")
    sm.add_option('chamber')
    sm.add_option('category')
    
    def truncate(name):
        if len(name) < 130: return name
        return name[0:127] + "..."
    
    def safe_strftime(date, format):
        return date.replace(year=3456).strftime(format).replace("3456", str(date.year)).replace(" 12:00AM", "")

    sm.add_left_column("Vote and Date", lambda vote, form : conditional_escape(vote.name()) + mark_safe("<br/>") + conditional_escape(safe_strftime(vote.created, "%b %d, %Y %I:%M%p")))
    sm.add_bottom_column(lambda vote, form : vote.summary())
    sm.add_column("Description and Result", lambda vote, form : truncate(vote.question))
    
    return sm

from django.shortcuts import redirect, get_object_or_404, Http404
from django.db.models import Count
from cache_utils.decorators import cached
from common.decorators import render_to

import re, json, urllib
from datetime import datetime, timedelta

from events.models import Feed
from states.models import StateBill, StateChamberEnum
import us
import openstates_metadata
from settings import SUNLIGHTLABS_API_KEY

from smartsearch.manager import SearchManager

import django.contrib.sitemaps
class sitemap(django.contrib.sitemaps.Sitemap):
	changefreq = "weekly"
	priority = 0.5
	
	def __init__(self, statesession):
		self.statesession = statesession
	
	def items(self):
		return StateBill.objects.filter(state_session=self.statesession).select_related('state_session').only('state_session__state', 'state_session__slug', 'bill_number')

def cache_result(f):
	"""A decorator that caches the result of a function with the function so that on further invocations
	it returns the value immediately."""
	def g(*args, **kwargs):
		if hasattr(f, "_cached_result"):
			return f._cached_result
		f._cached_result = f(*args, **kwargs)
		return f._cached_result
	return g

@render_to('states/bill.html')
def state_bill(request, state, session, billnum):
	bill = get_object_or_404(StateBill, state_session__state=state, state_session__slug=session, bill_number=billnum)
	state = bill.state_session.state
	state_metadata = openstates_metadata.stata_metadata[state]
	
	chamber_name = ""
	if bill.chamber == StateChamberEnum.lower:
		chamber_name = state_metadata["lower_chamber_name"]
	if bill.chamber == StateChamberEnum.upper:
		chamber_name = state_metadata["upper_chamber_name"]
		
	@cache_result
	def openstates_api_info():
		try:
			if bill.openstatesid == None: return None
			os_state, os_session, os_bill = bill.openstatesid.split(" ", 2)
			state_chamber = { StateChamberEnum.lower: "lower/", StateChamberEnum.upper: "upper/" }
			url = "http://openstates.org/api/v1/bills/%s/%s/%s%s?apikey=%s" \
				% (os_state, os_session, state_chamber.get(bill.chamber, ""), os_bill, SUNLIGHTLABS_API_KEY)
			print url
			return json.load(urllib.urlopen(url))
		except:
			return None
			
	def get_feed():
		return Feed.objects.get(feedname="states_bill:%d" % bill.id)
			
	return {
		"bill": bill,
		"state_metadata": state_metadata,
		"chamber_name": chamber_name,
		"openstates_api_info": openstates_api_info, # as a function to allow for template-level caching
		"feed": get_feed,
	}

@render_to('states/state.html')
def state_overview(request, state):
	if state.upper() not in us.statenames:
		raise Http404()
		
	try:
		feed = Feed.objects.get(feedname="states_%s_bills" % state)
	except Feed.DoesNotExist:
		feed = None
		
	return {
		"state": state.upper(),
		"state_metadata": openstates_metadata.stata_metadata[state.upper()],
		"feed": feed,
	}

def state_bill_browse(request, state):
	if state != "" and state.upper() not in us.statenames:
		raise Http404()
	
	sm = SearchManager(StateBill, connection="states")

	if state: sm.add_filter('state', state)

	sm.add_option('text', label='search title & summary', type="text", choices="NONE")
	if not state: sm.add_option('state', label="state", type="select", sort="KEY", formatter=lambda k : k.upper())
	sm.add_option('state_session', label="session", type="select", sort=lambda k : (datetime.now().date() - k.startdate) if k.startdate else timedelta(days=0), visible_if=lambda post:state or "state" in post, formatter=lambda k : k.name) # use now to make reverse sort
	sm.add_option('chamber', label="chamber")
	
	return sm.view(request, "states/bill_search.html",
		defaults={
			"text": request.GET.get("text", ""),
		},
		noun = ("state bill", "state bills"),
		context = {
			"state": state.upper(),
			"statename": us.statenames.get(state.upper(), None),
		},
		)

_states_with_data = None
def states_with_data():
	global _states_with_data
	if not _states_with_data:
		from haystack.query import SearchQuerySet
		_states_with_data = sorted([s[0].upper() for s in SearchQuerySet().using('states').filter(indexed_model_name__in=["StateBill"]).facet('state').facet_counts()['fields']['state']])
	return _states_with_data


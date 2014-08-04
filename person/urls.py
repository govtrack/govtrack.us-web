# -*- coding: utf-8 -*-
from django.conf.urls import *
from bill.views import bill_details

urlpatterns = patterns('person.views',
    url(r'^$', 'membersoverview'),
    url(r'^map$', 'browse_map', name="person_list"),
	url(r'^(current|all)$', 'searchmembers', name="person_search"),

	# must put things that could look like names of members of congress first
	url(r'^report-cards/(\d{4})(?:/([^/\.]+)(?:/([^/\.]+))?)?$', 'person_session_stats_overview', name='person_session_stats_overview'),
	url(r'^report-cards/(\d{4})/([^/]+)/([^/\.]+).csv$', 'person_session_stats_export', name='person_session_stats_export'),

    url(r'^([A-Za-z]+)/?$', 'browse_state'), # Wikipedia has bad links using state names instead of abbrs, so we support it
    url(r'^([A-Za-z]+)/(\d{1,2})/?$', 'browse_district'), # Wikipedia has bad links using state names instead of abbrs, so we support it

	url(r'^[^/]+/(\d+)$', 'person_details', name='person_details'), # name slug (but it's ignored) "/" ID
    url(r'^([A-Z]?\d+)$', 'person_details', name='person_details'), # allow bioguide ID here
	url(r'^[^/]+/(\d+)/report-card/(\d{4})', 'person_session_stats', name='person_session_stats'), # name slug "/" ID "/year-end/" session name (year)
	
    url(r'^ajax/district_lookup$', 'district_lookup'),
    url(r'^ajax/homepage_summary$', 'homepage_summary'),
	url(r'^embed/mapframe(?:\.xpd)?$', 'districtmapembed', name='districtmapembed'),
)

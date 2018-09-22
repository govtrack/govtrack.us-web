# -*- coding: utf-8 -*-
from django.conf.urls import url

import person.views

urlpatterns = [
    url(r'^$', person.views.membersoverview),
    url(r'^map$', person.views.browse_map, name="person_list"),
	url(r'^(current|all)$', person.views.searchmembers, name="person_search"),

	# must put things that could look like names of members of congress first
	url(r'^report-cards/(\d{4})(?:/([^/\.]+)(?:/([^/\.]+))?)?$', person.views.person_session_stats_overview, name='person_session_stats_overview'),
	url(r'^report-cards/(\d{4})/([^/]+)/([^/\.]+).csv$', person.views.person_session_stats_export, name='person_session_stats_export'),

    url(r'^([A-Za-z]+)/?$', person.views.browse_state), # Wikipedia has bad links using state names instead of abbrs, so we support it
    url(r'^([A-Za-z]+)/(\d{1,2})/?$', person.views.browse_district), # Wikipedia has bad links using state names instead of abbrs, so we support it

	url(r'^[^/]+/(\d+)$', person.views.person_details, name='person_details'), # name slug (but it's ignored) "/" ID
    url(r'^([A-Z]?\d+)$', person.views.person_details, name='person_details'), # allow bioguide ID here
	url(r'^[^/]+/(\d+)/report-card/(\d{4})', person.views.person_session_stats, name='person_session_stats'), # name slug "/" ID "/year-end/" session name (year)
	url(r'^[^/]+/(\d+)/cosponsors', person.views.person_cosponsors),
	
	url(r'^embed/mapframe(?:\.xpd)?$', person.views.districtmapembed, name='districtmapembed'),

	url(r'^lookup\.json$', person.views.lookup_reps),
]
# -*- coding: utf-8 -*-
from django.urls import re_path

import person.views

urlpatterns = [
    re_path(r'^$', person.views.membersoverview),
    re_path(r'^map$', person.views.browse_map, name="person_list"),
    re_path(r'^(current|all)$', person.views.searchmembers, name="person_search"),

    # must put things that could look like names of members of congress first
    re_path(r'^report-cards/(\d{4})(?:/([^/\.]+)(?:/([^/\.]+))?)?$', person.views.person_session_stats_overview, name='person_session_stats_overview'),
    re_path(r'^report-cards/(\d{4})/([^/]+)/([^/\.]+).csv$', person.views.person_session_stats_export, name='person_session_stats_export'),
    re_path(r'^missing', person.views.missing_legislators),

    re_path(r'^([A-Za-z]+)/?$', person.views.browse_state), # Wikipedia has bad links using state names instead of abbrs, so we support it
    re_path(r'^([A-Za-z]+)/(\d{1,2})/?$', person.views.browse_district), # Wikipedia has bad links using state names instead of abbrs, so we support it
    re_path(r'^([A-Za-z]{2})/(\d{1,2}).png$', person.views.district_map_static_image), # Wikipedia has bad links using state names instead of abbrs, so we support it

    re_path(r'^[^/]+/(\d+)$', person.views.person_details, name='person_details'), # name slug (but it's ignored) "/" ID
    re_path(r'^([A-Z]?\d+)$', person.views.person_details, name='person_details'), # allow bioguide ID here
    re_path(r'^[^/]+/(\d+)/report-card/(\d{4})', person.views.person_session_stats, name='person_session_stats'), # name slug "/" ID "/year-end/" session name (year)
    re_path(r'^[^/]+/(\d+)/cosponsors', person.views.person_cosponsors),

    re_path(r'^embed/mapframe(?:\.xpd)?$', person.views.districtmapembed, name='districtmapembed'),

    re_path(r'^lookup-district\.json$', person.views.lookup_district),
    re_path(r'^lookup\.json$', person.views.lookup_reps),
]

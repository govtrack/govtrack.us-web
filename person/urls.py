# -*- coding: utf-8 -*-
from django.conf.urls.defaults import *
from bill.views import bill_details

urlpatterns = patterns('person.views',
    url(r'^$', 'browsemembersbymap', name="person_list"),
	url(r'^(current|all)$', 'searchmembers', name="person_search"),

    url(r'^(?:([A-Za-z]+)(?:/(\d+))?)?/?$', 'browsemembersbymap'), # Wikipedia has bad links using state names instead of abbrs, so we support it
	url(r'^[^/]+/(\d+)', 'person_details', name='person_details'),
	
    url(r'^ajax/district_lookup$', 'district_lookup'),
	url(r'^embed/mapframe(?:\.xpd)?$', 'districtmapembed', name='districtmapembed'),
)

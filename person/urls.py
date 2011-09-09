# -*- coding: utf-8 -*-
from django.conf.urls.defaults import *
from bill.views import bill_details

urlpatterns = patterns('person.views',
    url(r'^$', 'browsemembersbymap', name="person_list"),
	url(r'^(all|search)$', 'searchmembers', name="person_search"),

    url(r'^(?:([A-Z][A-Z])(?:/(\d+))?)?$', 'browsemembersbymap'),
	url(r'^[^/]+/(\d+)', 'person_details', name='person_details'),
	
    url(r'^spectrum$', 'political_spectrum', name='political_spectrum'),
	
	url(r'^embed/mapframe(?:\.xpd)?$', 'districtmapembed', name='districtmapembed'),
)

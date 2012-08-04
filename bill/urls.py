# -*- coding: utf-8 -*-
from django.conf.urls.defaults import *

urlpatterns = patterns('bill.views',
    url(r'^browse$', 'bill_list', name='bill_list'),
    url(r'^(\d+)/([a-z]+)(\d+)$', 'bill_details', name='bill_details'),
    url(r'^(\d+)/([a-z]+)(\d+)/text(?:/([a-z0-9]+))?$', 'bill_text', name='bill_text'),
	url(r'^subjects/([^/]+)/(\d+)', 'subject', name='person_details'),
    url(r'^$', 'bill_docket', name='bill_docket'),
    url(r'^_ajax/market_test_vote', 'market_test_vote'),
    url(r'^_ajax/load_text', 'bill_text_ajax'),
    url(r'^_ajax/join_community', 'join_community'),
)

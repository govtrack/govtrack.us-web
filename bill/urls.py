# -*- coding: utf-8 -*-
from django.conf.urls.defaults import *

urlpatterns = patterns('bill.views',
    url(r'^browse$', 'bill_list', name='bill_list'),
    url(r'^(\d+)/([a-z]+)(\d+)$', 'bill_details', name='bill_details'),
    url(r'^(\d+)/([a-z]+)(\d+)/text$', 'bill_text', name='bill_text'),
	url(r'^subjects/([^/]+)/(\d+)', 'subject', name='person_details'),
    url(r'^$', 'bill_docket', name='bill_docket'),
    url(r'^_ajax/market_test_vote', 'market_test_vote'),
)

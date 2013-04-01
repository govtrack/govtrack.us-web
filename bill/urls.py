# -*- coding: utf-8 -*-
from django.conf.urls.defaults import *

urlpatterns = patterns('bill.views',
    url(r'^browse$', 'bill_list', name='bill_list'),
    url(r'^(\d+)/([a-z]+)(\d+)$', 'bill_details', name='bill_details'),
    url(r'^(\d+)/([a-z]+)(\d+)/text(?:/([a-z0-9]+))?$', 'bill_text', name='bill_text'),
    url(r'^(\d+)/([a-z]+)(\d+)/advocacy$', 'bill_advocacy_tips'),
	url(r'^subjects/([^/]+)/(\d+)', 'subject', name='person_details'),
    url(r'^$', 'bill_docket', name='bill_docket'),
    url(r'^_ajax/market_test_vote', 'market_test_vote'),
    url(r'^_ajax/load_text', 'bill_text_ajax'),
    url(r'^_ajax/join_community', 'join_community'),
    url(r'^_admin/go_to_summary_admin', 'go_to_summary_admin', name="bill_go_to_summary_admin"),
)

urlpatterns += patterns('bill.aprilfools',
    url(r'^_ajax/april_fools', 'bill_or_not'),
)

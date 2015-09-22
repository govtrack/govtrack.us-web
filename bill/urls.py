# -*- coding: utf-8 -*-
from django.conf.urls import *

urlpatterns = patterns('bill.views',
    url(r'^browse$', 'bill_list', name='bill_list'),
    url(r'^(\d+)/([a-z]+)(\d+)$', 'bill_details', name='bill_details'),
    url(r'^(\d+)/([a-z]+)(\d+)/summary$', 'bill_summaries', name='bill_summaries'),
    url(r'^(\d+)/([a-z]+)(\d+)/text(?:/([a-z0-9]+))?$', 'bill_text', name='bill_text'),
    url(r'^(\d+)/([a-z]+)(\d+)/widget$', 'bill_widget_info'),
    url(r'^(\d+)/([a-z]+)(\d+)/widget\.html$', 'bill_widget'),
    url(r'^(\d+)/([a-z]+)(\d+)/widget\.js$', 'bill_widget_loader'),
    url(r'^(\d+)/([a-z]+)(\d+).json$', 'bill_get_json', name='bill_get_json'),
    url(r'^subjects/([^/]+)/(\d+)', 'subject'),
    url(r'^$', 'bill_docket', name='bill_docket'),
    url(r'^statistics$', 'bill_statistics', name='bill_stats'),
    url(r'^uscode(?:/(\d+|.*))?$', 'uscodeindex'),
    url(r'^_ajax/market_test_vote', 'market_test_vote'),
    url(r'^_ajax/load_text', 'bill_text_ajax'),
    url(r'^_ajax/join_community', 'join_community'),
    url(r'^_admin/go_to_summary_admin', 'go_to_summary_admin', name="bill_go_to_summary_admin"),
    url(r'^_redirect/start-poll', 'start_poll', name="bill_start_poll"),
    url(r'^(\d+)/([a-z]+)(\d+)/(thumbnail|_text_image)$', 'bill_text_image'),
)

urlpatterns += patterns('',
    url(r'^real_or_not', 'bill.bill_or_not.bill_or_not'),
    url(r'^_ajax/bill_or_not', 'bill.bill_or_not.load_game'),
)

# -*- coding: utf-8 -*-
from django.conf.urls import url

import bill.views

urlpatterns = [
    url(r'^browse$', bill.views.bill_list, name='bill_list'),
    url(r'^(\d+)/([a-z]+)(\d+)$', bill.views.bill_details, name='bill_details'),
    url(r'^(\d+)/([a-z]+)(\d+)/summary$', bill.views.bill_summaries, name='bill_summaries'),
    url(r'^(\d+)/([a-z]+)(\d+)/details$', bill.views.bill_full_details, name='bill_full_details'),
    url(r'^(\d+)/([a-z]+)(\d+)/cosponsors$', bill.views.bill_cosponsors, name='bill_full_details'),
    url(r'^(\d+)/([a-z]+)(\d+)/studyguide$', bill.views.bill_key_questions, name='bill_key_questions'),
    url(r'^(\d+)/([a-z]+)(\d+)/text(?:/([a-z0-9-]+))?$', bill.views.bill_text, name='bill_text'),
    url(r'^(\d+)/([a-z]+)(\d+)/widget$', bill.views.bill_widget_info),
    url(r'^(\d+)/([a-z]+)(\d+)/widget\.html$', bill.views.bill_widget),
    url(r'^(\d+)/([a-z]+)(\d+)/widget\.js$', bill.views.bill_widget_loader),
    url(r'^(\d+)/([a-z]+)(\d+)/comment$', bill.views.bill_contact_congress),
    url(r'^(\d+)/([a-z]+)(\d+).json$', bill.views.bill_get_json, name='bill_get_json'),
    url(r'^subjects/([^/]+)/(\d+)', bill.views.subject),
    url(r'^$', bill.views.bills_overview, name='bills_overview'),
    url(r'^statistics$', bill.views.bill_statistics, name='bill_stats'),
    url(r'^uscode(?:/(\d+|.*))?$', bill.views.uscodeindex),
    url(r'^_ajax/load_text', bill.views.bill_text_ajax),
    url(r'^_ajax/join_community', bill.views.join_community),
    url(r'^_admin/go_to_summary_admin', bill.views.go_to_summary_admin, name="bill_go_to_summary_admin"),
    url(r'^(\d+)/([a-z]+)(\d+)/(thumbnail|_text_image|card)$', bill.views.bill_text_image),
]


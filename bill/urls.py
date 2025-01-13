# -*- coding: utf-8 -*-
from django.urls import re_path

import bill.views

urlpatterns = [
    re_path(r'^browse$', bill.views.bill_list, name='bill_list'),
    re_path(r'^(\d+)/([a-z]+)(\d+)$', bill.views.bill_details, name='bill_details'),
    re_path(r'^(\d+)/([a-z]+)(\d+)/summary$', bill.views.bill_summaries, name='bill_summaries'),
    re_path(r'^(\d+)/([a-z]+)(\d+)/details$', bill.views.bill_full_details, name='bill_full_details'),
    re_path(r'^(\d+)/([a-z]+)(\d+)/cosponsors$', bill.views.bill_cosponsors, name='bill_full_details'),
    re_path(r'^(\d+)/([a-z]+)(\d+)/studyguide$', bill.views.bill_key_questions, name='bill_key_questions'),
    re_path(r'^(\d+)/([a-z]+)(\d+)/text(?:/([a-z0-9-]+))?$', bill.views.bill_text, name='bill_text'),
    re_path(r'^(\d+)/([a-z]+)(\d+)/widget$', bill.views.bill_widget_info),
    re_path(r'^(\d+)/([a-z]+)(\d+)/widget\.html$', bill.views.bill_widget),
    re_path(r'^(\d+)/([a-z]+)(\d+)/widget\.js$', bill.views.bill_widget_loader),
    re_path(r'^(\d+)/([a-z]+)(\d+)/comment$', bill.views.bill_contact_congress),
    re_path(r'^(\d+)/([a-z]+)(\d+).json$', bill.views.bill_get_json, name='bill_get_json'),
    re_path(r'^subjects/([^/]+)/(\d+)', bill.views.subject),
    re_path(r'^$', bill.views.bills_overview, name='bills_overview'),
    re_path(r'^statistics$', bill.views.bill_statistics, name='bill_stats'),
    re_path(r'^uscode(?:/(\d+|.*))?$', bill.views.uscodeindex),
    re_path(r'^_ajax/load_text', bill.views.bill_text_ajax),
    re_path(r'^_ajax/join_community', bill.views.join_community),
    re_path(r'^_admin/go_to_summary_admin', bill.views.go_to_summary_admin, name="bill_go_to_summary_admin"),
    re_path(r'^(\d+)/([a-z]+)(\d+)/(thumbnail|_text_image|card)$', bill.views.bill_text_image),
]


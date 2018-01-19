# -*- coding: utf-8 -*-
from django.conf.urls import url

import vote.views

urlpatterns = [
    url('^votes$', vote.views.vote_list, name='vote_list'),
    url('^votes/(\d+)-(\w+)/(h|s)(\d+)$', vote.views.vote_details, name='vote_details'),
    url('^votes/(\d+)-(\w+)/(h|s)(\d+)/export/csv$', vote.views.vote_export_csv, name='vote_export_csv'),
    url('^votes/(\d+)-(\w+)/(h|s)(\d+)/export/xml$', vote.views.vote_export_xml, name='vote_export_xml'),
    url('^votes/(\d+)-(\w+)/(h|s)(\d+).json$', vote.views.vote_get_json, name='vote_get_json'),
    url('^votes/(\d+)-(\w+)/(h|s)(\d+)/(diagram|thumbnail|map)$', vote.views.vote_thumbnail_image, name='vote_thumbnail_image'),
    url('^votes/check_thumbnails', vote.views.vote_check_thumbnails),
    url('^votes/presidential-candidates', vote.views.presidential_candidates),
    url('^votes/compare/(\d+)/([\w\-]+)$', vote.views.vote_comparison_table_named),
    url('^votes/compare/([\d,]+)$', vote.views.vote_comparison_table_arbitrary),
    url('^_admin/go_to_vote_summary_admin', vote.views.go_to_summary_admin, name="vote_go_to_summary_admin"),
]

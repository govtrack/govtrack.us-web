# -*- coding: utf-8 -*-
from django.urls import re_path

import vote.views

urlpatterns = [
    re_path('^votes$', vote.views.vote_list, name='vote_list'),
    re_path('^votes/(\d+)-(\w+)/(h|s)(\d+)$', vote.views.vote_details, name='vote_details'),
    re_path('^votes/(\d+)-(\w+)/(h|s)(\d+)/export/csv$', vote.views.vote_export_csv, name='vote_export_csv'),
    re_path('^votes/(\d+)-(\w+)/(h|s)(\d+).json$', vote.views.vote_get_json, name='vote_get_json'),
    re_path('^votes/(\d+)-(\w+)/(h|s)(\d+)/(diagram|map|thumbnail|card)$', vote.views.vote_thumbnail_image, name='vote_thumbnail_image'),
    re_path('^votes/check_thumbnails', vote.views.vote_check_thumbnails),
    re_path('^votes/presidential-candidates', vote.views.presidential_candidates),
    re_path('^votes/compare/(\d+)/([\w\-]+)$', vote.views.vote_comparison_table_named),
    re_path('^votes/compare/_add$', vote.views.vote_comparison_table_arbitrary_add),
    re_path('^votes/compare/([\w\.,-]+)$', vote.views.vote_comparison_table_arbitrary),
    re_path('^_admin/go_to_vote_summary_admin', vote.views.go_to_summary_admin, name="vote_go_to_summary_admin"),
]

# -*- coding: utf-8 -*-
from django.conf.urls import *

urlpatterns = patterns('vote.views',
    url('^votes$', 'vote_list', name='vote_list'),
    url('^votes/(\d+)-(\w+)/(h|s)(\d+)$', 'vote_details', name='vote_details'),
    url('^votes/(\d+)-(\w+)/(h|s)(\d+)/export/csv$', 'vote_export_csv', name='vote_export_csv'),
    url('^votes/(\d+)-(\w+)/(h|s)(\d+)/export/xml$', 'vote_export_xml', name='vote_export_xml'),
    url('^votes/(\d+)-(\w+)/(h|s)(\d+).json$', 'vote_get_json', name='vote_get_json'),
    url('^votes/(\d+)-(\w+)/(h|s)(\d+)/(diagram|thumbnail|map)$', 'vote_thumbnail_image', name='vote_thumbnail_image'),
    url('^votes/check_thumbnails', 'vote_check_thumbnails'),
    url('^votes/presidential-candidates', 'presidential_candidates'),
    url('^votes/compare/(\d+)/([\w\-]+)$', 'vote_comparison_table'),
    url('^_admin/go_to_vote_summary_admin', 'go_to_summary_admin', name="vote_go_to_summary_admin"),
)

# -*- coding: utf-8 -*-
from django.conf.urls.defaults import *

urlpatterns = patterns('vote.views',
    url('^votes$', 'vote_list', name='vote_list'),
    url('^votes/(\d+)-(\w+)/(h|s)(\d+)$', 'vote_details', name='vote_details'),
    url('^votes/(\d+)-(\w+)/(h|s)(\d+)/export/csv$', 'vote_export_csv', name='vote_export_csv'),
    url('^votes/(\d+)-(\w+)/(h|s)(\d+)/export/xml$', 'vote_export_xml', name='vote_export_xml'),
    url('^votes/(\d+)-(\w+)/(h|s)(\d+)/thumbnail$', 'vote_thumbnail_image', name='vote_thumbnail_image'),
    url('^votes/check_thumbnails', 'vote_check_thumbnails'),
)

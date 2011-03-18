# -*- coding: utf-8 -*-
from django.conf.urls.defaults import *

urlpatterns = patterns('vote.views',
    url('^congress/votes$', 'vote_list', name='vote_list'),
    url('^congress/votes/(\d+)-(\w+)/(h|s)(\d+)$', 'vote_details', name='vote_details'),
    url('^congress/votes/(\d+)-(\w+)/(h|s)(\d+)/export/csv$', 'vote_export_csv', name='vote_export_csv'),
    url('^congress/votes/(\d+)-(\w+)/(h|s)(\d+)/export/xml$', 'vote_export_xml', name='vote_export_xml'),
)

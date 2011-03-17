# -*- coding: utf-8 -*-
from django.conf.urls.defaults import *

urlpatterns = patterns('vote.views',
    url('^congress/votes$', 'vote_list', name='vote_list'),
    url('^congress/votes/(\d+)-(\w+)/(h|s)(\d+)$', 'vote_details', name='vote_details'),
)

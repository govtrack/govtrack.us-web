# -*- coding: utf-8 -*-
from django.conf.urls.defaults import *

urlpatterns = patterns('vote.views',
    url('^congress/votes', 'vote_list', name='vote_list'),
)

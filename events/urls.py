# -*- coding: utf-8 -*-
from django.conf.urls.defaults import *

urlpatterns = patterns('events.views',
    url('^events$', 'events_list', name='events_list'),
    url('^events/search_feeds$', 'search_feeds', name='search_feeds'),
    url('^events/rss$', 'events_rss'),
)

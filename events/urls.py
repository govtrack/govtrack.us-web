# -*- coding: utf-8 -*-
from django.conf.urls.defaults import *

urlpatterns = patterns('events.views',
    url('^events$', 'events_list', name='events_list'),
    url('^events/_load_events$', 'events_list_items', name='events_list_items'),
    url('^events/search_feeds$', 'search_feeds', name='search_feeds'),
    url('^events/events.rss$', 'events_rss'),
)

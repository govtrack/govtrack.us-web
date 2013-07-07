# -*- coding: utf-8 -*-
from django.conf.urls import *

urlpatterns = patterns('events.views',
    url(r'^accounts/lists', 'edit_subscription_lists'),
    url(r'^events/_edit', 'edit_subscription_list'),
    url('^events/_load_events$', 'events_list_items', name='events_list_items'),
    url('^events/events.rss$', 'events_rss'),
    url('^events/embed_legacy$', 'events_embed_legacy'),
    url('^events/([\w\-]+)$', 'events_show_feed'),
    url('^start$', 'events_add_tracker'),
    url('^events/_ajax/start/search$', 'start_search'),
)


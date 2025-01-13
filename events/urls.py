# -*- coding: utf-8 -*-
from django.urls import re_path

import events.views

urlpatterns = [
    re_path(r'^accounts/lists', events.views.edit_subscription_lists),
    re_path(r'^events/_edit', events.views.edit_subscription_list),
    re_path('^events/_load_events$', events.views.events_list_items, name='events_list_items'),
    re_path('^events/events.rss$', events.views.events_rss),
    re_path('^events/embed_legacy$', events.views.events_embed_legacy),
    re_path('^events/_save_list_note$', events.views.save_list_note),
    re_path('^events/([\w\-]+)$', events.views.events_show_feed),
]

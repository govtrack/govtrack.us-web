# -*- coding: utf-8 -*-
from django.conf.urls import url

import events.views

urlpatterns = [
    url(r'^accounts/lists', events.views.edit_subscription_lists),
    url(r'^events/_edit', events.views.edit_subscription_list),
    url('^events/_load_events$', events.views.events_list_items, name='events_list_items'),
    url('^events/events.rss$', events.views.events_rss),
    url('^events/embed_legacy$', events.views.events_embed_legacy),
    url('^events/_save_list_note$', events.views.save_list_note),
    url('^events/([\w\-]+)$', events.views.events_show_feed),
]
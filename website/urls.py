# -*- coding: utf-8 -*-
from django.conf.urls import url

import website.views

urlpatterns = [
    url(r'^$', website.views.index, name='index'),
    url(r'^(start|about|about-our-data|contact|press|advertising|legal|developers|developers/downstream|developers/data|developers/license|developers/rsync|what-is-the-law|how-a-bill-becomes-a-law|congressional-procedures|sousveillance|reading-list)$', website.views.staticpage, name='staticpage'),
    #url(r'^developers/api$', website.views.api_overview),
    url(r'^congress/?$', website.views.congress_home, name='congress_home'),
    url(r'^search$', website.views.search, name='search'),
    url(r'^events/syndication-feed', website.views.push_to_social_media_rss),
    url(r'^accounts/docket', website.views.your_docket),
    url(r'^accounts/update_settings', website.views.update_account_settings),
    url(r'^accounts/unsubscribe/([A-Za-z0-9]{10,64})', website.views.account_one_click_unsubscribe),
    url(r'^about/analysis', website.views.analysis_methodology),
    url(r'^about/financial', website.views.financial_report),
    url(r'^accounts/membership$', website.views.go_ad_free_start),
    url(r'^accounts/membership/start$', website.views.go_ad_free_redirect),
    url(r'^accounts/membership/finish$', website.views.go_ad_free_finish),
    url(r'^accounts/positions', website.views.get_user_position_list),
    url(r'^accounts/_set_district$', website.views.set_district),
    url(r'^videos(?:/(?P<video_id>[a-z0-9\-_]+))?', website.views.videos),
    url(r'^medium-post-redirector/(\d+)?', website.views.medium_post_redirector),
    url(r'^_ajax/update-position', website.views.update_userposition, name='update-userposition'),
    url(r'^_ajax/reaction', website.views.add_remove_reaction, name='reaction'),
    url(r'^reactions.json', website.views.dump_reactions, name='dump_reactions'),
    url(r'^sousveillance.json', website.views.dump_sousveillance),
    url(r'^misconduct', website.views.misconduct),
]

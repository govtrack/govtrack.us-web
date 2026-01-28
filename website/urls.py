# -*- coding: utf-8 -*-
from django.urls import re_path

import website.views

urlpatterns = [
    re_path(r'^$', website.views.index, name='index'),
    re_path(r'^(start|about|about-our-data|contact|press|advertising|legal|what-is-the-law|how-a-bill-becomes-a-law|congressional-procedures|reading-list|how-to-use|for-hill-staff|for-advocates|for-journalists|for-educators|rewards)$', website.views.staticpage, name='staticpage'),
    #re_path(r'^developers/api$', website.views.api_overview),
    re_path(r'^congress/?$', website.views.congress_home, name='congress_home'),
    re_path(r'^search$', website.views.search, name='search'),
    re_path(r'^search/_autocomplete$', website.views.search_autocomplete),
    re_path(r'^accounts/docket', website.views.your_docket),
    re_path(r'^accounts/update_settings', website.views.update_account_settings),
    re_path(r'^accounts/unsubscribe/([A-Za-z0-9]{10,64})', website.views.account_one_click_unsubscribe),
    re_path(r'^about/analysis', website.views.analysis_methodology),
    re_path(r'^about/financial', website.views.financial_report),
    re_path(r'^accounts/membership$', website.views.go_ad_free_start),
    re_path(r'^accounts/membership/checkout$', website.views.go_ad_free_checkout),
    re_path(r'^accounts/membership/webhook$', website.views.go_ad_free_webhook),
    re_path(r'^accounts/positions', website.views.get_user_position_list),
    re_path(r'^accounts/community/login', website.views.discourse_sso),
    re_path(r'^videos(?:/(?P<video_id>[a-z0-9\-_]+))?', website.views.videos),
    re_path(r'^_ajax/update-position', website.views.update_userposition, name='update-userposition'),
    re_path(r'^_ajax/reaction', website.views.add_remove_reaction, name='reaction'),
    re_path(r'^reactions.json', website.views.dump_reactions, name='dump_reactions'),
    re_path(r'^misconduct', website.views.misconduct),
    re_path(r'^user-group-signup', website.views.user_group_signup),
    re_path(r'^missing-data', website.views.missing_data),
    re_path(r'^covid-19', website.views.covid19),
    re_path(r'^community-forum/_ajax/post', website.views.community_forum_post_message),
    re_path(r'^posts.rss', website.views.BlogPostsFeed()),
    re_path(r'^posts(?:/(?:(?P<category>analysis|news)|(?P<id>\d+)/(?P<slug>[a-z0-9\-_]+)))?$', website.views.posts),
]

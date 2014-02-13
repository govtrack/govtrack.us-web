# -*- coding: utf-8 -*-
from django.conf.urls import *

urlpatterns = patterns('website.views',
    url(r'^$', 'index', name='index'),
    url(r'^(start|about|press|advertising|legal|developers|developers/downstream|developers/data|developers/license|developers/rsync|developers/people_xml|developers/vote_xml|developers/bill_xml|civicimpulse|blog_template)$', 'staticpage', name='staticpage'),
    url(r'^developers/api$', 'api_overview'),
    url(r'^congress/?$', 'congress_home', name='congress_home'),
    url(r'^congress/live$', 'congress_live', name='congress_live'),
    url(r'^search$', 'search', name='search'),
    #url(r'^campaigns/bulkdata', 'campaign_bulk_data'),
    url(r'^events/syndication-feed', 'push_to_social_media_rss'),
    url(r'^accounts/docket', 'your_docket'),
    url(r'^accounts/update_settings', 'update_account_settings'),
    url(r'^about/analysis', 'analysis_methodology'),
    url(r'^about/financial', 'financial_report'),
    url(r'^accounts/go_ad_free$', 'go_ad_free_start'),
    url(r'^accounts/go_ad_free/start$', 'go_ad_free_redirect'),
    url(r'^accounts/go_ad_free/finish$', 'go_ad_free_finish'),
    url(r'^videos(?:/(?P<video_id>[a-z0-9\-_]+))?', 'videos'),
)


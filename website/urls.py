# -*- coding: utf-8 -*-
from django.conf.urls.defaults import *

urlpatterns = patterns('website.views',
    url(r'^$', 'index', name='index'),
    url(r'^(overview|about|press|sources|advertising|tools|developers|developers/downstream|developers/data|developers/license|developers/rsync|developers/people_xml|developers/vote_xml|developers/bill_xml|civicimpulse|blog_template)$', 'staticpage', name='staticpage'),
    url(r'^developers/api$', 'api_overview'),
    url(r'^congress/?$', 'congress_home', name='congress_home'),
    url(r'^search$', 'search', name='search'),
    #url(r'^campaigns/bulkdata', 'campaign_bulk_data'),
    url(r'^events/syndication-feed', 'push_to_social_media_rss'),
)


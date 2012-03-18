# -*- coding: utf-8 -*-
from django.conf.urls.defaults import *

urlpatterns = patterns('website.views',
    url(r'^$', 'index', name='index'),
    url(r'^(overview|about|press|sources|advertising|developers|developers/downstream|developers/data|developers/license|civicimpulse)$', 'staticpage', name='staticpage'),
    url(r'^congress/?$', 'congress_home', name='congress_home'),
    url(r'^search$', 'search', name='search'),
    url(r'^campaigns/bulkdata', 'campaign_bulk_data'),
)


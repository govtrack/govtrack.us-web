# -*- coding: utf-8 -*-
from django.conf.urls.defaults import *

urlpatterns = patterns('website.views',
    url(r'^$', 'index', name='index'),
    url(r'^(about|press|sources|advertising|developers|developers/downstream|developers/data|developers/license)$', 'staticpage', name='staticpage'),
    url(r'^congress$', 'congress_home', name='congress_home'),
    url(r'^search$', 'search', name='search'),
)


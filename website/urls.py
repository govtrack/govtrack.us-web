# -*- coding: utf-8 -*-
from django.conf.urls.defaults import *

urlpatterns = patterns('website.views',
    url(r'^$', 'index', name='index'),
    url(r'^about$', 'about', name='about'),
    url(r'^congress/members(?:/([A-Z]+)(?:/(\d+))?)?$', 'browsemembers', name='browsemembers'),
    url(r'^congress$', 'congress_home', name='congress_home'),
)

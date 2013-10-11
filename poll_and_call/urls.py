# -*- coding: utf-8 -*-
from django.conf.urls import *

urlpatterns = patterns('poll_and_call.views',
    url(r'^([a-z0-9\-\_]+)$', 'issue_show'),
    url(r'^([a-z0-9\-\_]+)/join/(\d+)$', 'issue_join'),
)


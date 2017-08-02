# -*- coding: utf-8 -*-
from django.conf.urls import *

urlpatterns = patterns('twostream.views',
    url(r'^user-head$', 'user_head', name='twostream-views-user-head'),
)


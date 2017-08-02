# -*- coding: utf-8 -*-
from django.conf.urls import url

import twostream.views

urlpatterns = [
    url(r'^user-head$', twostream.views.user_head, name='twostream-views-user-head'),
]
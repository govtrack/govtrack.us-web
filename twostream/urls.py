# -*- coding: utf-8 -*-
from django.urls import re_path

import twostream.views

urlpatterns = [
    re_path(r'^user-head$', twostream.views.user_head, name='twostream-views-user-head'),
]

# -*- coding: utf-8 -*-
from django.urls import re_path

import committee.views

urlpatterns = [
    re_path(r'^$', committee.views.committee_list, name='committee_list'),
    re_path(r'^calendar$', committee.views.committee_calendar, name='committee_calendar'),
    re_path(r'^game', committee.views.game, name='game'),
    re_path(r'^(\w+)$', committee.views.committee_details, name='committee_details'),
    re_path(r'^(\w+)/(\w+)$', committee.views.committee_details, name='subcommittee_details'),
]

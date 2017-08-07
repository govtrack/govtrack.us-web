# -*- coding: utf-8 -*-
from django.conf.urls import url

import committee.views

urlpatterns = [
    url(r'^$', committee.views.committee_list, name='committee_list'),
    url(r'^calendar$', committee.views.committee_calendar, name='committee_calendar'),
    url(r'^(\w+)$', committee.views.committee_details, name='committee_details'),
    url(r'^(\w+)/(\w+)$', committee.views.committee_details, name='subcommittee_details'),
]
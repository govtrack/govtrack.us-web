# -*- coding: utf-8 -*-
from django.conf.urls import *

urlpatterns = patterns('committee.views',
    url(r'^$', 'committee_list', name='committee_list'),
    url(r'^(\w+)$', 'committee_details', name='committee_details'),
    url(r'^(\w+)/(\w+)$', 'committee_details', name='subcommittee_details'),
)

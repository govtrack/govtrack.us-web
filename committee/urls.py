# -*- coding: utf-8 -*-
from django.conf.urls.defaults import *

urlpatterns = patterns('committee.views',
    url(r'congress/committees/(\w+)$', 'committee_details', name='committee_details'),
    url(r'congress/committees/(\w+)/(\w+)$', 'committee_details', name='subcommittee_details'),
)

# -*- coding: utf-8 -*-
from django.urls import re_path

import redirect.views

urlpatterns = [
    re_path(r'^congress/person\.xpd$', redirect.views.person_redirect, name='person_redirect'),
    re_path(r'^congress/(?:findyourreps|replookup)\.xpd$', redirect.views.district_maps_redirect),
    re_path(r'^congress/committee\.xpd$', redirect.views.committee_redirect, name='committee_redirect'),
    re_path(r'^congress/bill(text)?\.xpd$', redirect.views.bill_redirect, name='bill_redirect'),
    re_path(r'^congress/billsearch\.xpd', redirect.views.bill_search_redirect),
    re_path(r'^congress/legislation.xpd', redirect.views.bill_overview_redirect),
    re_path(r'^congress/subjects\.xpd', redirect.views.subject_redirect),
    re_path(r'^congress/vote\.xpd', redirect.views.vote_redirect),
    re_path(r'^congress/votes\.xpd', redirect.views.votes_redirect),
]

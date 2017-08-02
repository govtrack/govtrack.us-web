# -*- coding: utf-8 -*-
from django.conf.urls import url

import redirect.views

urlpatterns = [
    url(r'^congress/person\.xpd$', redirect.views.person_redirect, name='person_redirect'),
    url(r'^congress/(?:findyourreps|replookup)\.xpd$', redirect.views.district_maps_redirect),
    url(r'^congress/committee\.xpd$', redirect.views.committee_redirect, name='committee_redirect'),
    url(r'^congress/bill(text)?\.xpd$', redirect.views.bill_redirect, name='bill_redirect'),
    url(r'^congress/billsearch\.xpd', redirect.views.bill_search_redirect),
    url(r'^congress/legislation.xpd', redirect.views.bill_overview_redirect),
    url(r'^congress/subjects\.xpd', redirect.views.subject_redirect),
    url(r'^congress/vote\.xpd', redirect.views.vote_redirect),
    url(r'^congress/votes\.xpd', redirect.views.votes_redirect),
]

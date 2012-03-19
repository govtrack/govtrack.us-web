# -*- coding: utf-8 -*-
from django.conf.urls.defaults import *

urlpatterns = patterns('redirect.views',
    url(r'^congress/person\.xpd$', 'person_redirect', name='person_redirect'),
    url(r'^congress/findyourreps\.xpd$', 'district_maps_redirect'),
    url(r'^congress/committee\.xpd$', 'committee_redirect', name='committee_redirect'),
    url(r'^congress/bill(text)?\.xpd$', 'bill_redirect', name='bill_redirect'),
    url(r'^congress/billsearch\.xpd', "bill_search_redirect"),
    url(r'^congress/legislation.xpd', "bill_overview_redirect"),
    url(r'^congress/subjects\.xpd', "subject_redirect"),
    url(r'^congress/vote\.xpd', "vote_redirect"),
    url(r'^congress/votes\.xpd', "votes_redirect"),
)

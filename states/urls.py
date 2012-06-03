# -*- coding: utf-8 -*-
from django.conf.urls.defaults import *

urlpatterns = patterns('states.views',
    url(r'^([a-z]{2})/bills/([^/]+)/(.+)$', 'state_bill'),
    url(r'^()bills/browse$', 'state_bill_browse'),
    url(r'^([a-z]{2})/bills/browse$', 'state_bill_browse'),
    url(r'^([a-z]{2})$', 'state_overview'),
)


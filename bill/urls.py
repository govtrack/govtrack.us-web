# -*- coding: utf-8 -*-
from django.conf.urls.defaults import *

urlpatterns = patterns('bill.views',
    url(r'^$', 'bill_list', name='bill_list'),
    url(r'^(\d+)/(\w+)(\d+)$', 'bill_details', name='bill_details'),
)

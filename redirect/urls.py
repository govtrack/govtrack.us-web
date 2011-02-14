# -*- coding: utf-8 -*-
from django.conf.urls.defaults import *

urlpatterns = patterns('redirect.views',
    url(r'congress/person\.xpd', 'person_redirect', name='person_redirect'),
)

# -*- coding: utf-8 -*-
from django.conf.urls import *

urlpatterns = patterns("event_calendar.views",
	url(r"", "calendar", name='calendar'),
)

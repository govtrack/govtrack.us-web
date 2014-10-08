# -*- coding: utf-8 -*-
from django.conf.urls import *

urlpatterns = patterns('whipturk.views',
    url(r'^my-calls$', 'my_calls'),
    url(r'^start-call$', 'start_call'),
    url(r'^_ajax/start-call$', 'dial'),
    url(r'^_ajax/call-status$', 'call_status'),
    url(r'^_ajax/update-report$', 'update_report'),
    url(r'^_twilio/call-(?P<method>start|input|transfer-end|end)/(?P<call_id>\d+)$', 'twilio_callback'),
)

# -*- coding: utf-8 -*-
from django.conf.urls import *

urlpatterns = patterns('poll_and_call.views',
    url(r'^([a-z0-9\-\_]+)$', 'issue_show'),
    url(r'^([a-z0-9\-\_]+)/join/(\d+)$', 'issue_join'),
    url(r'^([a-z0-9\-\_]+)/make_call$', 'issue_make_call'),
    url(r'^_ajax/start-call$', 'start_call'),
    url(r'^_ajax/poll-call-status$', 'poll_call_status'),
    url(r'^_twilio/call-start/(\d+)$', 'twilio_call_start'),
    url(r'^_twilio/call-input/(\d+)$', 'twilio_call_input'),
    url(r'^_twilio/call-transfer-end/(\d+)$', 'twilio_call_transfer_ended'),
    url(r'^_twilio/call-end/(\d+)$', 'twilio_call_end'),
)


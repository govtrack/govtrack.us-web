from django.urls import re_path

import oversight.views

urlpatterns = [
    re_path(r'^$', oversight.views.oversight_topic_list),
    re_path(r'^(\d+)-([a-z0-9-_]+)$', oversight.views.oversight_topic_details),
]


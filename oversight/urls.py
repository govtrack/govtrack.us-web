from django.conf.urls import url

import oversight.views

urlpatterns = [
    url(r'^$', oversight.views.oversight_topic_list),
    url(r'^(\d+)-([a-z0-9-_]+)$', oversight.views.oversight_topic_details),
]


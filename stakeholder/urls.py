from django.conf.urls import url

import stakeholder.views

urlpatterns = [
    url(r'^$', stakeholder.views.list_my_stakeholders),
    url(r'^new-post$', stakeholder.views.new_stakeholder_post),
    url(r'^.*/(\d+)$', stakeholder.views.view_stakeholder),
]

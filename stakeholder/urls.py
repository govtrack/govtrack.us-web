from django.urls import re_path

import stakeholder.views

urlpatterns = [
    re_path(r'^$', stakeholder.views.list_my_stakeholders),
    re_path(r'^new-post$', stakeholder.views.new_stakeholder_post),
    re_path(r'^.*/(\d+)$', stakeholder.views.view_stakeholder),
]

from django.conf.urls import url

import stakeholder.views

urlpatterns = [
    url(r'^new$', stakeholder.views.new_stakeholder),
    url(r'^.*/(\d+)$', stakeholder.views.view_stakeholder),
]

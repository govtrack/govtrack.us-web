from django.conf.urls import url, include
from django.conf import settings

from userpanels.views import *

urlpatterns = [
    url(r'^$', list_panels),
    url(r'^(\d+)$', show_panel),
    url(r'^(\d+)/edit$', change_panel),
    url(r'^(\d+)/users$', export_panel_users),
    url(r'^join/([\w-]+)$', accept_invitation),
]

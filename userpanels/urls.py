from django.conf.urls import url, include
from django.conf import settings

from userpanels.views import *

urlpatterns = [
    url(r'^$', list_panels),
    url(r'^(\d+)$', show_panel),
    url(r'^(\d+)/edit$', change_panel),
    url(r'^(\d+)/export/(members|positions)$', export_panel_user_data),
    url(r'^join/([\w-]+)$', accept_invitation),
]

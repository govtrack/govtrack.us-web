from django.urls import re_path, include
from django.conf import settings

from userpanels.views import *

urlpatterns = [
    re_path(r'^$', list_panels),
    re_path(r'^(\d+)$', show_panel),
    re_path(r'^(\d+)/edit$', change_panel),
    re_path(r'^(\d+)/export/(members|positions)$', export_panel_user_data),
    re_path(r'^join/([\w-]+)$', accept_invitation),
]

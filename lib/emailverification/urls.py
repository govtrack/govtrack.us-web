from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^code/([0-9A-Z]+)$', 'emailverification.views.processcode'),
    (r'^code/delete/([0-9A-Z]+)$', 'emailverification.views.killcode'),
)


from django.conf.urls.defaults import *
from django.conf import settings
import django.views.static

from django.contrib import admin
admin.autodiscover()


urlpatterns = patterns('',
    url(r'^admin/', include(admin.site.urls)),
    url(r'^%s(?P<path>.*)$' % settings.MEDIA_URL.lstrip('/'),
        django.views.static.serve, {'document_root': settings.MEDIA_ROOT}),

    # Server only sertain directories from data directory
    url(r'^(data/photos/.*)$',
        django.views.static.serve, {'document_root': settings.ROOT}),
    url(r'^(data/us/112/stats/person/sponsorshipanalysis/.*)$',
        django.views.static.serve, {'document_root': settings.ROOT}),
    url(r'', include('redirect.urls')),
    url(r'', include('website.urls')),
    url(r'^congress/members(?:$|/)', include('person.urls')),
    url(r'^congres/committees/', include('committee.urls')),
    url(r'^congress/', include('vote.urls')),
    url(r'^congress/bills/', include('bill.urls')),
    url(r'', include('events.urls')),

    # django-registration-pv
    (r'^emailverif/', include('emailverification.urls')),
    (r'^registration/', include('registration.urls')),
    (r'^accounts/login$', 'registration.views.loginform'),
    (r'^accounts/logout$', 'django.contrib.auth.views.logout'),
    (r'^accounts/profile/change_password$', 'django.contrib.auth.views.password_change'),
    (r'^accounts/profile/password_changed$', 'django.contrib.auth.views.password_change_done'),

    # django-haystack search
    (r'^search/', include('haystack.urls')),
)

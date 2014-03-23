from django.conf.urls import *
from django.conf import settings
import django.views.static

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    url(r'^admin/', include(admin.site.urls)),

	# main URLs
    url(r'', include('redirect.urls')),
    url(r'', include('website.urls')),
    url(r'^congress/members(?:$|/)', include('person.urls')),
    url(r'^congress/committees/', include('committee.urls')),
    url(r'^congress/', include('vote.urls')),
    url(r'^congress/bills/', include('bill.urls')),
    url(r'', include('events.urls')),
    url(r'^market/', include('predictionmarket.urls')),
    url(r'^states(/|$)', include('states.urls')),
    url(r'^poll(/|$)', include('poll_and_call.urls')),
    url(r'^api/v2/([^/]+)(?:/(\d+))?', 'website.api.apiv2'),

    url(r'^_twostream', include('twostream.urls')),

    # django-registration-pv
    (r'^emailverif/', include('emailverification.urls')),
    (r'^registration/', include('registration.urls')),
    (r'^accounts/login/?$', 'registration.views.loginform'), # Django adds a slash when logging out?
    (r'^accounts/logout$', 'django.contrib.auth.views.logout', { "redirect_field_name": "next" }),
    (r'^accounts/profile$', 'registration.views.profile'),
)

# sitemaps
from collections import OrderedDict
import person.views, bill.views, committee.views, vote.views, states.models, states.views
from django.contrib.sitemaps.views import index as sitemap_index_view
from django.contrib.sitemaps.views import sitemap as sitemap_map_view
from twostream.decorators import anonymous_view
sitemaps = OrderedDict([
        ("bills_current", bill.views.sitemap_current),
        #("bills_archive", bill.views.sitemap_archive), # takes too long to load
        ("people_current", person.views.sitemap_current),
        ("people_archive", person.views.sitemap_archive),
        ("districts", person.views.sitemap_districts),
        ("committees", committee.views.sitemap),
        ("votes_current", vote.views.sitemap_current),
        #("votes_archive", vote.views.sitemap_archive), # takes too long to load
	])
urlpatterns += patterns('',
    (r'^sitemap\.xml$', anonymous_view(sitemap_index_view), {'sitemaps': sitemaps, 'sitemap_url_name': 'sitemap_pages'}),
   url(r'^sitemap-(?P<section>.+)\.xml$', anonymous_view(sitemap_map_view), {'sitemaps': sitemaps}, name='sitemap_pages'),
)

# API access points
from website.api import v1_api
urlpatterns += patterns('',
    (r'^api/', include(v1_api.urls)),
)

# static files during debugging
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
urlpatterns += staticfiles_urlpatterns()

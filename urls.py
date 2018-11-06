from django.conf.urls import url, include
from django.conf import settings
import django.views.static

from django.contrib import admin

from django.contrib.auth import views as auth_views
import registration.views
import website.api
import website.views

urlpatterns = [
    url(r'^admin/', admin.site.urls),

	# main URLs
    url(r'', include('redirect.urls')),
    url(r'', include('website.urls')),
    url(r'^congress/members(?:$|/)', include('person.urls')),
    url(r'^congress/committees/', include('committee.urls')),
    url(r'^congress/', include('vote.urls')),
    url(r'^congress/bills/', include('bill.urls')),
    url(r'', include('events.urls')),
    url(r'^api/v2/([^/]+)(?:/(\d+))?', website.api.apiv2),
    url(r'^panels/', include('userpanels.urls')),
    url(r'^stakeholders/', include('stakeholder.urls')),

    url(r'^_twostream/', include('twostream.urls')),

    # django-registration-pv
    url(r'^emailverif/', include('emailverification.urls')),
    url(r'^registration/', include('registration.urls')),
    url(r'^accounts/login/?$', registration.views.loginform), # Django adds a slash when logging out?
    url(r'^accounts/logout$', auth_views.LogoutView.as_view(), { "redirect_field_name": "next" }),
    url(r'^accounts/profile$', registration.views.profile, name='registration.views.profile'),

	url(r'^dump_request', website.views.dumprequest),
]

# sitemaps
from collections import OrderedDict
import person.views, bill.views, committee.views, vote.views
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
urlpatterns += [
    url(r'^sitemap\.xml$', anonymous_view(sitemap_index_view), {'sitemaps': sitemaps, 'sitemap_url_name': 'sitemap_pages'}),
    url(r'^sitemap-(?P<section>.+)\.xml$', anonymous_view(sitemap_map_view), {'sitemaps': sitemaps}, name='sitemap_pages'),
]

if settings.DEBUG:
    # serve /static during debugging
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns
    urlpatterns += staticfiles_urlpatterns()
 
    # serve /data during debugging
    from django.conf.urls.static import static
    urlpatterns += static("/data", document_root="data")

    # serve the debug toolbar
    import debug_toolbar
    urlpatterns = [
        url(r'^__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns

if "silk" in settings.INSTALLED_APPS:
	urlpatterns += [url(r'^silk/', include('silk.urls', namespace='silk'))]


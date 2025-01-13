from django.urls import re_path, include
from django.conf import settings
import django.views.static

from django.contrib import admin

from django.contrib.auth import views as auth_views

import registration.views
import website.api
import website.views
import events.views
from person.views import person_details, other_people_list

urlpatterns = []

# OTP-enabled login for staff access to the Django admin (and their own accounts), overriding the default login page
from django.contrib.auth.views import LoginView
from django_otp.forms import OTPAuthenticationForm
urlpatterns += [
    re_path(r'^admin/login/?$', LoginView.as_view(authentication_form=OTPAuthenticationForm, template_name="login_otp.html")),
]

urlpatterns += [
    re_path(r'^admin/', admin.site.urls),
    re_path('markdownx/', include('markdownx.urls')),

    # main URLs
    re_path(r'', include('redirect.urls')),
    re_path(r'', include('website.urls')),
    re_path(r'^congress/members(?:$|/)', include('person.urls')),
    re_path(r'^congress/committees/', include('committee.urls')),
    re_path(r'^congress/', include('vote.urls')),
    re_path(r'^congress/bills/', include('bill.urls')),
    re_path(r'^congress/other-people/(presidents|vice-presidents)$', other_people_list),
    re_path(r'^congress/other-people/[^/]+/(\d+)$', person_details),
    re_path(r'', include('events.urls')),
    re_path(r'^api/v2/([^/]+)(?:/(\d+))?', website.api.apiv2),
    re_path(r'^panels/', include('userpanels.urls')),
    re_path(r'^list/([A-Za-z0-9]+)$', events.views.view_list),

    re_path(r'^_twostream/', include('twostream.urls')),

    # django-registration-pv
    re_path(r'^emailverif/', include('emailverification.urls')),
    re_path(r'^registration/', include('registration.urls')),
    re_path(r'^accounts/login/?$', registration.views.loginform), # Django adds a slash when logging out?
    re_path(r'^accounts/logout$', auth_views.LogoutView.as_view(), { "redirect_field_name": "next" }),
    re_path(r'^accounts/profile$', registration.views.profile, name='registration.views.profile'),

    re_path(r'^dump_request', website.views.dumprequest),
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
    re_path(r'^sitemap\.xml$', anonymous_view(sitemap_index_view), {'sitemaps': sitemaps, 'sitemap_url_name': 'sitemap_pages'}),
    re_path(r'^sitemap-(?P<section>.+)\.xml$', anonymous_view(sitemap_map_view), {'sitemaps': sitemaps}, name='sitemap_pages'),
]

if settings.DEBUG:
    # serve /static during debugging
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns
    urlpatterns += staticfiles_urlpatterns()
 
    # serve /data during debugging
    from django.conf.urls.static import static
    urlpatterns += static("/data", document_root="data")

if "silk" in settings.INSTALLED_APPS:
	urlpatterns += [re_path(r'^silk/', include('silk.urls', namespace='silk'))]


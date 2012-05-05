from django.conf.urls.defaults import *
from django.conf import settings
import django.views.static

from django.contrib import admin
admin.autodiscover()

# define sitemaps
import person.views, bill.views, committee.views, vote.views
sitemaps = {
        "bills_current": bill.views.sitemap_current,
        "bills_previous": bill.views.sitemap_previous,
        #"bills_archive": bill.views.sitemap_archive, # takes too long to load
        "people_current": person.views.sitemap_current,
        "people_archive": person.views.sitemap_archive,
        "districts": person.views.sitemap_districts,
        "committees": committee.views.sitemap,
        "votes_current": vote.views.sitemap_current,
        "votes_previous": vote.views.sitemap_previous,
        #"votes_archive": vote.views.sitemap_archive, # takes too long to load
    }
    
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
    url(r'^congress/committees/', include('committee.urls')),
    url(r'^congress/', include('vote.urls')),
    url(r'^congress/bills/', include('bill.urls')),
    url(r'', include('events.urls')),
    url(r'^market/', include('predictionmarket.urls')),

    # django-registration-pv
    (r'^emailverif/', include('emailverification.urls')),
    (r'^registration/', include('registration.urls')),
    (r'^accounts/login/?$', 'registration.views.loginform'), # Django adds a slash when logging out?
    (r'^accounts/logout$', 'django.contrib.auth.views.logout', { "redirect_field_name": "next" }),
    (r'^accounts/profile$', 'registration.views.profile'),
    
    # etcetera
    (r'^sitemap\.xml$', 'django.contrib.sitemaps.views.index', {'sitemaps': sitemaps}),
    (r'^sitemap-(?P<section>.+)\.xml$', 'django.contrib.sitemaps.views.sitemap', {'sitemaps': sitemaps}),
)

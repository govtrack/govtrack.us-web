# -*- coding: utf-8 -*-
import os
import sys
import re
import datetime

sys.path.insert(0, 'lib')

DEBUG = ("DEBUG" in os.environ)
INTERNAL_IPS = ('127.0.0.1',)

ADMINS = []
MANAGERS = ADMINS

if DEBUG and "SSH_CONNECTION" in os.environ:
	# When launched from an SSH session, add the remote host to
	# the list of INTERNAL_IPSs so that he can see the SQL.
	# debugging output.
	INTERNAL_IPS = ('127.0.0.1', os.environ["SSH_CONNECTION"].split(" ")[0])
	if sys.argv == ['./manage.py', 'runserver']: print("Internal IPs:", repr(INTERNAL_IPS))

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'America/New_York'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = 'media'

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = '/media/'

STATIC_URL = '/static/'
STATICFILES_DIRS = ['static']

# django-regitration-pv
APP_NICE_SHORT_NAME = "GovTrack" # a short name for your site
SITE_ROOT_URL = "https://www.govtrack.us"
LOGIN_REDIRECT_URL = "/accounts/profile"
SERVER_EMAIL = "GovTrack.us <noreply@alerts.GovTrack.us>" # From: address on verification emails, error emails
DEFAULT_FROM_EMAIL = SERVER_EMAIL # send_email management command
REGISTRATION_ASK_USERNAME = False
SECURE_PROXY_SSL_HEADER = ("HTTPS", "on")

SESSION_COOKIE_AGE = 6*604800 # seconds in six weeks
SESSION_COOKIE_SECURE = not DEBUG # send session cookies over SSL only
CSRF_COOKIE_SECURE = not DEBUG # similarly
SESSION_SERIALIZER = 'django.contrib.sessions.serializers.PickleSerializer' # needed by openid login

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
EMAIL_SUBJECT_PREFIX = '[GovTrack] '

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    #'debug_toolbar.middleware.DebugToolbarMiddleware',
    'twostream.middleware.CacheLogic',
    'website.middleware.GovTrackMiddleware',
]

ROOT_URLCONF = 'urls'

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.admin',
    'django.contrib.humanize',
    'django.contrib.sitemaps',
    'django.contrib.staticfiles',
    'django.contrib.messages',

    # 3rd party libraries
    'common',
    #'south',
    #'debug_toolbar',
    #'silk',
    'crispy_forms',

    'haystack',
    'htmlemailer',
    
    # project modules
    'twostream',
    'simplegetapi',
    'person',
    'committee',
    'website',
    'vote',
    'parser',
    'events',
    'smartsearch',
    'bill',
    'oversight',
    'userpanels',
    'stakeholder',

    # for django-registration-pv
    'emailverification',
    'registration',
]

# in production...
try:
    import django_mysql
    INSTALLED_APPS.append("django_mysql")
except ImportError:
    pass

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend', # only used for the admin?
    'registration.views.EmailPasswordLoginBackend', # regular login
    'registration.views.DirectLoginBackend', # social login
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': ['templates'],
        'OPTIONS': {
            'debug': DEBUG,
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.static',
                'events.middleware.template_context_processor',
                'website.middleware.template_context_processor',
            ],
            'loaders': [
                    'django.template.loaders.filesystem.Loader',
                    'django.template.loaders.app_directories.Loader',
                ],
        },
    },
]

CRISPY_TEMPLATE_PACK = 'bootstrap3'

TEST_DATABASE_CHARSET = 'utf8'
TEST_RUNNER = 'django.test.runner.DiscoverRunner'

DATETIME_FORMAT = 'M j, Y P'
DATE_FORMAT = 'M j, Y'

SEND_BROKEN_LINK_EMAILS = False
IGNORABLE_404_ENDS = ('spinner.gif', 'billtext/images/quote.png')
IGNORABLE_404_STARTS = ('/phpmyadmin/',)
import re
IGNORABLE_404_URLS = (
	re.compile(r'^/phpmyadmin/'),
	re.compile(r'spinner\.gif'),
	re.compile(r'billtext/images/quote.png$'),
	)

CURRENT_CONGRESS = 116
CURRENT_ELECTION_DATE = datetime.date(2020, 11, 3)

EMAIL_UPDATES_FROMADDR = "GovTrack.us Email Updates <noreply@alerts.GovTrack.us>"
EMAIL_UPDATES_RETURN_PATH = "GovTrack.us Email Updates <bounces+uid=%d@alerts.GovTrack.us>"

# Load settings from the environment
from settings_env import *

if not SECRET_KEY:
    raise Exception('You must provide SECRET_KEY value in an env variable')

# Since we rely on external APIs in a few places, make sure
# that downed APIs elsewhere don't hold us too long. Not
# sure this has any useful effect. Also affects outbound SMTP?
import socket
socket.setdefaulttimeout(20.0)

# Restrict silk profile information to staff users. Don't
# log request/response bodies because we will go crazy in
# production.
SILKY_AUTHENTICATION = True
SILKY_AUTHORISATION = True
SILKY_MAX_REQUEST_BODY_SIZE = 0
SILKY_MAX_RESPONSE_BODY_SIZE = 0
SILKY_META = True
SILKY_INTERCEPT_PERCENT = 1
SILKY_PYTHON_PROFILER = True

SHOW_TOOLBAR_CALLBACK = lambda : True

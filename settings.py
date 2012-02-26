# -*- coding: utf-8 -*-
import os
import os.path
import sys

ROOT = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(ROOT, 'lib'))

DEBUG = not ("RELEASE" in os.environ)
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    ('Joshua Tauberer', 'tauberer@govtrack.us'),
)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

MANAGERS = ADMINS

if "SSH_CONNECTION" in os.environ:
	# When launched from an SSH session, add the remote host to
	# the list of INTERNAL_IPSs so that he can see the SQL.
	# debugging output.
	INTERNAL_IPS = ('127.0.0.1', os.environ["SSH_CONNECTION"].split(" ")[0])
	print "Internal IPs:", repr(INTERNAL_IPS)
                                        
# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'Europe/Moscow'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = os.path.join(ROOT, 'static')

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = '/static/'

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/static/admin-media/'


# django-regitration-pv
APP_NICE_SHORT_NAME = "GovTrack" # a short name for your site
SITE_ROOT_URL = "http://test.govtrack.us"
LOGIN_REDIRECT_URL = "/"
SERVER_EMAIL = "GovTrack <noreply@GovTrack.us>" # From: address on verification emails
REGISTRATION_ASK_USERNAME = False
RECAPTCHA_PUBLIC_KEY = "6LcK-McSAAAAAG0pmM3wQR3kbAMM6NXhwera2UNg"
RECAPTCHA_PRIVATE_KEY = "6LcK-McSAAAAAHtd7v2SCtd-oIV-ZVarJYidlmFj"
GOOGLE_OAUTH_TOKEN = "..."
GOOGLE_OAUTH_TOKEN_SECRET = "..."
GOOGLE_OAUTH_SCOPE = "http://www.google.com/m8/feeds/contacts/default/full&quot;" # can be an empty string
TWITTER_OAUTH_TOKEN = "zcuFN74ydyl0h5tduGxdA"
TWITTER_OAUTH_TOKEN_SECRET = "F7fuPicBKJmgX4UGR1kmy6dRugGjRy24rVxGsWmg"
LINKEDIN_API_KEY = "..."
LINKEDIN_SECRET_KEY = "..."
FACEBOOK_APP_ID = "..."
FACEBOOK_APP_SECRET = "..."
FACEBOOK_AUTH_SCOPE = "email" # can be an empty string

#set the user profile for registration activation key
AUTH_PROFILE_MODULE = 'registration.UserProfile'

#dummy email backend through python -m -n -c DebuggingServer localhost:1025 /usr/bin/python: No module named -n
EMAIL_HOST = 'smtp.gmail.com'
#EMAIL_PORT =
EMAIL_HOST_USER = ''
EMAIL_HOST_PASSWORD = ''

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.load_template_source',
    'django.template.loaders.app_directories.load_template_source',
#     'django.template.loaders.eggs.load_template_source',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
)

ROOT_URLCONF = 'urls'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    os.path.join(ROOT, 'templates'),
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.admin',
    'django.contrib.humanize',
    # 3rd party libraries
    'common',
    'django_extensions',
    #'south',
    'GChartWrapper.charts',
    'debug_toolbar',
    # project modules
    'person',
    'committee',
    'website',
    'vote',
    'parser',
    'events',
    'smartsearch',
    'bill',

    # for django-registration-pv
    'emailverification',
    'registration',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.core.context_processors.auth',
    'django.core.context_processors.debug',
    'django.core.context_processors.i18n',
    'django.core.context_processors.media',
    'django.core.context_processors.request',
)

TEST_DATABASE_CHARSET = 'utf8'

CACHE_BACKEND = 'memcached://127.0.0.1:11211/'

DATETIME_FORMAT = 'M d, Y P'
DATE_FORMAT = 'M d, Y'

CURRENT_CONGRESS = 112

try:
    from settings_local import *
except ImportError:
    pass

if not SECRET_KEY:
    raise Exception('You must provide SECRET_KEY value in settings_local.py')


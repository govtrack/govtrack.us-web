import os
import os.path

# Normally you should not import ANYTHING from Django directly
# into your settings, but ImproperlyConfigured is an exception.
from django.core.exceptions import ImproperlyConfigured

NOT_SET = object()

def get_env_variable(var_name, default=NOT_SET):
    """ Get the environment variable or return exception """
    try:
        return os.environ[var_name]
    except KeyError:
        if default is NOT_SET:
            error_msg = "Set the {} environment variable".format(var_name)
            raise ImproperlyConfigured(error_msg)
        else:
            return default

def get_env_listvar(var_name, default=NOT_SET):
    strvalue = get_env_variable(var_name, default)
    return [item.strip() for item in strvalue.split(',')]

def get_env_boolvar(var_name, default=NOT_SET):
    strvalue = get_env_variable(var_name, default)
    return (strvalue.lower() == 'true')


ALLOWED_HOSTS = get_env_listvar('ALLOWED_HOSTS', default="localhost,127.0.0.1")
try:
    ADMINS = [("Site Owner", get_env_variable('ADMIN_EMAIL'))]
except ImproperlyConfigured:
    pass

import dj_database_url
DEFAULT_DATABASE_URL = 'sqlite:///' + os.path.dirname(__file__) + '/local/database.sqlite'
DATABASE_URL = get_env_variable('DATABASE_URL', DEFAULT_DATABASE_URL)
DATABASES = {
	'default': dj_database_url.parse(DATABASE_URL)
}

import django_cache_url
CACHE_URL = get_env_variable('CACHE_URL', default="locmem://opendataiscool")
CACHES = {
	'default': django_cache_url.parse(CACHE_URL)
}

import dj_haystack_url
HAYSTACK_CONNECTIONS = {
    'default': { # required but not used
        'ENGINE': 'haystack.backends.simple_backend.SimpleEngine',
    },
    'person': dj_haystack_url.parse(get_env_variable('HAYSTACK_PERSON_CONNECTION', default='xapian:local/xapian_index_person')),
    'bill': dj_haystack_url.parse(get_env_variable('HAYSTACK_BILL_CONNECTION', default='xapian:local/xapian_index_bill')),
}

CONGRESS_LEGISLATORS_PATH = get_env_variable('CONGRESS_LEGISLATORS_PATH', default='data/congress-legislators')
RSS_CAMPAIGN_QUERYSTRING = get_env_variable('RSS_CAMPAIGN_QUERYSTRING', default="?utm_campaign=govtrack_feed&utm_source=govtrack/feed&utm_medium=rss")

from django.utils.crypto import get_random_string
default_secret_key = get_random_string(50, 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)')
SECRET_KEY = get_env_variable('SECRET_KEY', default=default_secret_key)

# Copy some environment variables into the Django settings object.
copy_env_vars = [
    # For accounts logic.
    "RECAPTCHA_PUBLIC_KEY",
    "RECAPTCHA_PRIVATE_KEY",
    "TWITTER_OAUTH_TOKEN", # also for automated tweets and used to update @GovTrack/Members-of-Congress twitter list
    "TWITTER_OAUTH_TOKEN_SECRET",
    "FACEBOOK_APP_ID", # also used for Facebook widgets
    "FACEBOOK_APP_SECRET",
    "FACEBOOK_AUTH_SCOPE",
    "GOOGLE_APP_ID",
    "GOOGLE_APP_SECRET",
    "GOOGLE_AUTH_SCOPE",

    # For email...
    "EMAIL_HOST",
    "EMAIL_PORT",
    "EMAIL_HOST_USER",
    "EMAIL_HOST_PASSWORD",
    "EMAIL_USE_TLS",
    "EMAIL_BACKEND",

    # For us...
    "GOOGLE_ANALYTICS_KEY",
    "TWITTER_ACCESS_TOKEN", # for automated tweets and to update @GovTrack/Members-of-Congress twitter list
    "TWITTER_ACCESS_TOKEN_SECRET",
    "PAYPAL_CLIENT_MODE",
    "PAYPAL_CLIENT_ID",
    "PAYPAL_CLIENT_SECRET",
]
for var in copy_env_vars:
    val = get_env_variable(var, default='')
    if val != "":
        if var == "EMAIL_PORT": val = int(val)
        if var == "EMAIL_USE_TLS": val = (val.lower()=="true")
        locals()[var] = val

# The hide-the-ads payment requires Paypal integration:
if PAYPAL_CLIENT_ID:
    import paypalrestsdk
    paypalrestsdk.configure(mode=PAYPAL_CLIENT_MODE, client_id=PAYPAL_CLIENT_ID, client_secret=PAYPAL_CLIENT_SECRET)


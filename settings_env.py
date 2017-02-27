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


ALLOWED_HOSTS = get_env_listvar('ALLOWED_HOSTS')

import dj_database_url
DEFAULT_DATABASE_URL = 'sqlite:///' + os.path.dirname(__file__) + '/database.sqlite'
DATABASE_URL = get_env_variable('DATABASE_URL', DEFAULT_DATABASE_URL)
DATABASES = {
	'default': dj_database_url.parse(DATABASE_URL)
}

import django_cache_url
CACHE_URL = get_env_variable('CACHE_URL')
CACHES = {
	'default': django_cache_url.parse(CACHE_URL)
}

import dj_haystack_url
HAYSTACK_CONNECTIONS = {
    'default': { # required but not used
        'ENGINE': 'haystack.backends.simple_backend.SimpleEngine',
    },
    'person': dj_haystack_url.parse(get_env_variable('HAYSTACK_PERSON_CONNECTION', 'simple')),
    'bill': dj_haystack_url.parse(get_env_variable('HAYSTACK_BILL_CONNECTION', 'simple')),
    'states': dj_haystack_url.parse(get_env_variable('HAYSTACK_STATE_CONNECTION', 'simple')),
}

CONGRESS_LEGISLATORS_PATH = get_env_variable('CONGRESS_LEGISLATORS_PATH')
GEOIP_DB_PATH = None
RSS_CAMPAIGN_QUERYSTRING = get_env_variable('RSS_CAMPAIGN_QUERYSTRING')

SECRET_KEY = get_env_variable('SECRET_KEY')

GOOGLE_ANALYTICS_KEY = get_env_variable('GOOGLE_ANALYTICS_KEY')

SUNLIGHTLABS_API_KEY = get_env_variable('SUNLIGHTLABS_API_KEY')
YOUTUBE_API_KEY = get_env_variable('YOUTUBE_API_KEY')

# for registration
RECAPTCHA_PUBLIC_KEY = get_env_variable('RECAPTCHA_PUBLIC_KEY')
RECAPTCHA_PRIVATE_KEY = get_env_variable('RECAPTCHA_PRIVATE_KEY')
TWITTER_OAUTH_TOKEN = get_env_variable('TWITTER_OAUTH_TOKEN')
TWITTER_OAUTH_TOKEN_SECRET = get_env_variable('TWITTER_OAUTH_TOKEN_SECRET')
FACEBOOK_APP_ID = get_env_variable('FACEBOOK_APP_ID')
FACEBOOK_APP_SECRET = get_env_variable('FACEBOOK_APP_SECRET')
FACEBOOK_AUTH_SCOPE = get_env_variable('FACEBOOK_AUTH_SCOPE', default='')  # can be an empty string
TWILIO_ACCOUNT_SID = get_env_variable('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = get_env_variable('TWILIO_AUTH_TOKEN')

# The ad-free payment requires something like this:
#import paypalrestsdk
#paypalrestsdk.configure(mode="sandbox", client_id="...", client_secret="...")


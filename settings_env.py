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

###############################################################################

ALLOWED_HOSTS = get_env_listvar('ALLOWED_HOSTS', default="localhost,127.0.0.1")
try:
    ADMINS = [("Site Owner", get_env_variable('ADMIN_EMAIL'))]
except ImproperlyConfigured:
    pass

import dj_database_url
if not os.path.exists("local"): os.makedirs('local') # ensure directory for default sqlite db exists
DEFAULT_DATABASE_URL = 'sqlite:///' + os.path.dirname(__file__) + '/local/database.sqlite'
DATABASE_URL = get_env_variable('DATABASE_URL', DEFAULT_DATABASE_URL)
DATABASES = {
	'default': dj_database_url.parse(DATABASE_URL)
}
if DATABASES['default']['ENGINE'] == 'django.db.backends.mysql':
    DATABASES['default']['OPTIONS']['charset'] = 'utf8mb4' # MySQL's true Unicode character set
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

from django.utils.crypto import get_random_string
default_secret_key = get_random_string(50, 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)')
SECRET_KEY = get_env_variable('SECRET_KEY', default=default_secret_key)

RSS_CAMPAIGN_QUERYSTRING = get_env_variable('RSS_CAMPAIGN_QUERYSTRING', default="?utm_campaign=govtrack_feed&utm_source=govtrack/feed&utm_medium=rss")


# Copy some environment variables into the Django settings object.
copy_env_vars = [
    # For accounts logic.
    "RECAPTCHA_SITE_KEY",
    "RECAPTCHA_SECRET_KEY",
    "TWITTER_OAUTH_TOKEN", # also for automated tweets and used to update @GovTrack/Members-of-Congress twitter list
    "TWITTER_OAUTH_TOKEN_SECRET",
    "GOOGLE_APP_ID",
    "GOOGLE_APP_SECRET",
    "GOOGLE_AUTH_SCOPE",
    "GOOGLE_API_KEY",

    # For email (if one SMTP backend)...
    "EMAIL_HOST",
    "EMAIL_PORT",
    "EMAIL_HOST_USER",
    "EMAIL_HOST_PASSWORD",
    "EMAIL_USE_TLS",
    "EMAIL_BACKEND",
    "VOTERAMA_EMAIL_TO",

    # Various other accounts we have.
    "GOOGLE_ANALYTICS_KEY",
    "TWITTER_ACCESS_TOKEN", # for automated tweets and to update @GovTrack/Members-of-Congress twitter list
    "TWITTER_ACCESS_TOKEN_SECRET",
    "STRIPE_PUB_KEY", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET",
    "MAPBOX_ACCESS_TOKEN",
    "MAPBOX_MAP_STYLE",
    "MAPBOX_MAP_ID",
    "COMMUNITY_FORUM_URL",
    "COMMUNITY_FORUM_SSO_KEY",
    "PROPUBLICA_CONGRESS_API_KEY",
    "DRAFTABLE_ACCOUNT_ID",
    "DRAFTABLE_AUTH_TOKEN",
    "MASTODON_GOVTRACK_PUSH_BOT_ACCESS_TOKEN",
    "BLUESKY_USERNAME",
    "BLUESKY_PASSWORD",

    # Data paths.
    "CONGRESS_DATA_PATH",
    "CONGRESS_PROJECT_PATH",
    "MISCONDUCT_DATABASE_PATH",
    "PRONUNCIATION_DATABASE_PATH",
    "SCORECARDS_DATABASE_PATH",
    "DISTRICT_BBOXES_FILE",
    "DISTRICT_PMTILES_FILE",
]
for var in copy_env_vars:
    val = get_env_variable(var, default='')
    if val != "":
        if var == "EMAIL_PORT": val = int(val)
        if var == "EMAIL_USE_TLS": val = (val.lower()=="true")
        locals()[var] = val

# The hide-the-ads payment requires Stripe integration:
if locals().get("STRIPE_SECRET_KEY"):
    import stripe
    stripe.api_key = STRIPE_SECRET_KEY

# Multiple email backends?
from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend
EMAIL_BACKENDS = { }
i = 1
while "EMAIL_{}_HOST".format(i) in os.environ:
    backend_class = SMTPEmailBackend
    backend_args = {
        "host": get_env_variable("EMAIL_{}_HOST".format(i)),
        "port": int(get_env_variable("EMAIL_{}_PORT".format(i))),
        "username": get_env_variable("EMAIL_{}_HOST_USER".format(i)),
        "password": get_env_variable("EMAIL_{}_HOST_PASSWORD".format(i)),
        "use_tls": get_env_boolvar("EMAIL_{}_USE_TLS".format(i)),
    }
    def make_backend(backend_class, backend_args):
      def create_backend(*args, **kwargs):
        return backend_class(
          *args,
          **backend_args,
          **kwargs)
      return create_backend
    EMAIL_BACKENDS[str(i)] = make_backend(backend_class, backend_args)
    i += 1

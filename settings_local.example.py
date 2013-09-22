import os.path

ALLOWED_HOSTS = ["*"]

DATABASES = {
	'default': {
        'NAME': os.path.dirname(__file__) + '/database.sqlite',
        'ENGINE': 'django.db.backends.sqlite3',
   	}
}

CACHES = {
	'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'opendataiscool'
	}
}

HAYSTACK_CONNECTIONS = {
    'default': { # required but not used
        'ENGINE': 'haystack.backends.simple_backend.SimpleEngine',
    },
    'person': {
        'ENGINE': 'haystack.backends.simple_backend.SimpleEngine', # replace this
    },
    'bill': {
        'ENGINE': 'haystack.backends.simple_backend.SimpleEngine', # replace this
    },
    'states': {
        'ENGINE': 'haystack.backends.simple_backend.SimpleEngine', # replace this
    },
}                   

CONGRESS_LEGISLATORS_PATH='../congress-legislators/'
GEOIP_DB_PATH = None
RSS_CAMPAIGN_QUERYSTRING = "?utm_campaign=govtrack_feed&utm_source=govtrack/feed&utm_medium=rss"

SECRET_KEY = 'fill this in'

GOOGLE_ANALYTICS_KEY = 'fill this in' 

SUNLIGHTLABS_API_KEY = 'fill this in'
YOUTUBE_API_KEY = 'fill this in'

# for registration
RECAPTCHA_PUBLIC_KEY = "fill this in"
RECAPTCHA_PRIVATE_KEY = "fill this in"
TWITTER_OAUTH_TOKEN = "fill this in"
TWITTER_OAUTH_TOKEN_SECRET = "fill this in"
FACEBOOK_APP_ID = "fill this in"
FACEBOOK_APP_SECRET = "fill this in"
FACEBOOK_AUTH_SCOPE = "email" # can be an empty string

# The ad-free payment requires something like this:
#import paypalrestsdk
#paypalrestsdk.configure(mode="sandbox", client_id="...", client_secret="...")


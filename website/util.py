from django.conf import settings

def twitter_api_client():
    import tweepy
    auth = tweepy.OAuthHandler(settings.TWITTER_OAUTH_TOKEN, settings.TWITTER_OAUTH_TOKEN_SECRET) # a.k.a. consumer_key, consumer_secret
    auth.set_access_token(settings.TWITTER_ACCESS_TOKEN, settings.TWITTER_ACCESS_TOKEN_SECRET)
    return tweepy.API(auth)


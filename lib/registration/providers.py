#;encoding=utf-8
import settings

import oauth2 as oauth
import urlparse
import urllib
import simplejson as json
from xml.dom import minidom

from settings import SITE_ROOT_URL

########################################

# DEFAULT PROVIDERS #

providers = { }

providers["google_openid"] = \
	{	"displayname": "Google",
		"method": "openid2",
		"xrds": "https://www.google.com/accounts/o8/id",
		"extensions": {
			"http://specs.openid.net/auth/2.0/signon": {},
			"http://specs.openid.net/extensions/pape/1.0": { },
			"http://specs.openid.net/extensions/ui/1.0": { "icon": "true" },
			"http://openid.net/srv/ax/1.0": {
				"mode": "fetch_request",
				"required": "email",
				"type.email": "http://schema.openid.net/contact/email"
				},
			#"http://specs.openid.net/extensions/oauth/1.0": {
			#	"consumer": settings.GOOGLE_OAUTH_TOKEN,
			#	"scope": settings.GOOGLE_OAUTH_SCOPE
			#	}
			},
		"trust_email": True,
		"profile_uid": lambda profile : profile["id"],
		"logo_urls": [
			(16, "/static/icons/sm/google16.png"),
			(32, "/static/icons/sm/google32.png"),
			(48, "/static/icons/sm/google48.png"),
			],
		"sort_order": 0,
	}

try:
	def twitter_get_profile(access_token):
		client = create_oauth1_client("twitter", access_token)
		resp, content = client.request("https://api.twitter.com/1/users/show.json?user_id=" + access_token['user_id'], "GET")
		if resp['status'] != '200':
			raise Exception("OAuth Failed: Invalid response from Twitter on loading profile information.")
		return json.loads(content)
		
	providers["twitter"] = \
		{	"displayname": "Twitter",
			"method": "oauth1",
			"request_token_url": "https://api.twitter.com/oauth/request_token",
			"access_token_url": "https://api.twitter.com/oauth/access_token",
			"authenticate_url": "https://api.twitter.com/oauth/authenticate",
			"oauth_token": settings.TWITTER_OAUTH_TOKEN,
			"oauth_token_secret": settings.TWITTER_OAUTH_TOKEN_SECRET,
			"trust_email": True,
			"load_profile": twitter_get_profile,
			"profile_uid": lambda profile : profile["id"],
			"logo_urls": [
				(16, "/static/icons/sm/twitter16.png"),
				(32, "/static/icons/sm/twitter32.png"),
				(48, "/static/icons/sm/twitter48.png"),
				],
			"sort_order": 50,
		}
except:
	# silently fail if any of the settings aren't set
	pass

try:
	def google_get_profile(access_token):
		client = create_oauth1_client("google", access_token)
		resp, content = client.request("http://www.google.com/m8/feeds/contacts/default/full?max-results=0", "GET")
		if resp['status'] != '200':
			raise Exception("OAuth Failed: Invalid response from Google on loading profile information.")
		
		profile = { }
		xml = minidom.parseString(content)
		for node in xml.getElementsByTagName("author"):
			profile["email"] = node.getElementsByTagName("email")[0].firstChild.data
			profile["name"] = node.getElementsByTagName("name")[0].firstChild.data
			profile["screen_name"] = profile["email"][0:profile["email"].index("@")]
		return profile
		
	providers["google_oauth"] = \
		{	"displayname": "Google",
			"method": "oauth1",
			"request_token_url": "https://www.google.com/accounts/OAuthGetRequestToken",
			"access_token_url": "https://www.google.com/accounts/OAuthGetAccessToken",
			"authenticate_url": "https://www.google.com/accounts/OAuthAuthorizeToken",
			"additional_request_parameters": { "scope": settings.GOOGLE_OAUTH_SCOPE },
			"oauth_token": settings.GOOGLE_OAUTH_TOKEN,
			"oauth_token_secret": settings.GOOGLE_OAUTH_TOKEN_SECRET,
			"trust_email": True,
			"load_profile": google_get_profile,
			"profile_uid": lambda profile : profile["email"],
			"logo_urls": [
				(16, "/static/icons/sm/google16.png"),
				(32, "/static/icons/sm/google32.png"),
				(48, "/static/icons/sm/google48.png"),
				],
			"sort_order": 10,
			"login": False
		}
except:
	# silently fail if any of the settings aren't set
	pass

try:
	def linkedin_get_profile(access_token):
		client = create_oauth1_client("linkedin", access_token)
		resp, content = client.request("https://api.linkedin.com/v1/people/~:(id,first-name,last-name)", "GET")
		if resp['status'] != '200':
			raise Exception("OAuth Failed: Invalid response from LinkedIn on loading profile information.")
		
		profile = { }
		xml = minidom.parseString(content)
		profile["id"] = xml.getElementsByTagName("id")[0].firstChild.data
		profile["name"] = xml.getElementsByTagName("first-name")[0].firstChild.data + " " + xml.getElementsByTagName("last-name")[0].firstChild.data
		profile["screen_name"] = profile["name"].replace(" ", "")
		return profile

	providers["linkedin"] = \
		{	"displayname": "LinkedIn®",
			"method": "oauth1",
			"request_token_url": "https://api.linkedin.com/uas/oauth/requestToken",
			"access_token_url": "https://api.linkedin.com/uas/oauth/accessToken",
			"authenticate_url": "https://api.linkedin.com/uas/oauth/authorize",
			"oauth_token": settings.LINKEDIN_API_KEY,
			"oauth_token_secret": settings.LINKEDIN_SECRET_KEY,
			"load_profile": linkedin_get_profile,
			"profile_uid": lambda profile : profile["id"],
			"logo_urls": [
				(16, "/static/icons/sm/linkedin16.png"),
				(32, "/static/icons/sm/linkedin32.png"),
				(48, "/static/icons/sm/linkedin48.png"),
				],
			"sort_order": 100,
		}
except:
	# silently fail if any of the settings aren't set
	pass

try:
	def facebook_get_profile(access_token):
		ret = urllib.urlopen("https://graph.facebook.com/me?" + urllib.urlencode({"access_token": access_token["access_token"]}))
		if ret.getcode() != 200:
			raise Exception("Invalid response from Facebook on obtaining profile information.")
		profile = json.loads(ret.read())
		# normalize to get a default screen name field
		profile["screen_name"] = profile["name"].replace(" ", "")
		return profile
		
	providers["facebook"] = \
		{	"displayname": "Facebook",
			"method": "oauth2",
			"authenticate_url": "https://graph.facebook.com/oauth/authorize",
			"access_token_url": "https://graph.facebook.com/oauth/access_token",
			"additional_request_parameters": { "scope": settings.FACEBOOK_AUTH_SCOPE },
			"clientid": settings.FACEBOOK_APP_ID,
			"clientsecret": settings.FACEBOOK_APP_SECRET,
			"trust_email": True,
			"load_profile": facebook_get_profile,
			"profile_uid": lambda profile : profile["id"],
			"logo_urls": [
				(16, "/static/icons/sm/facebook16.png"),
				(32, "/static/icons/sm/facebook32.png"),
				(48, "/static/icons/sm/facebook48.png"),
				],
			"sort_order": 25,
		}
except:
	# silently fail if any of the settings aren't set
	pass


########################################

class UserCancelledAuthentication(Exception):
	pass

def openid2_get_redirect(request, provider, callback, scope, mode):
	xrds = urllib.urlopen(providers[provider]["xrds"])
	if xrds.getcode() != 200:
		raise Exception("OpenID Failed: Invalid response from " + providers[provider]["displayname"] + " on obtaining a XRDS information: " + xrds.read())
	xrds = xrds.read()
	
	from openid.consumer.consumer import Consumer
	from openid.consumer.discover import OpenIDServiceEndpoint
	from openid.store.memstore import MemoryStore
	
	service =  OpenIDServiceEndpoint.fromXRDS(providers[provider]["xrds"], xrds)[0]
	
	consumer = Consumer(request.session, MemoryStore())
	
	auth = consumer.beginWithoutDiscovery(service)
	
	if "extensions" in providers[provider]:
		for ext, d in providers[provider]["extensions"].iteritems():
			for k, v in d.iteritems():
				auth.addExtensionArg(ext, k, v) 
				
	if mode == "compact": # works with Google
		auth.addExtensionArg("http://specs.openid.net/extensions/ui/1.0", "mode", "popup")
	
	return auth.redirectURL(realm=SITE_ROOT_URL, return_to=callback)

def openid2_finish_authentication(request, provider, original_callback):
	from openid.consumer.consumer import Consumer, SUCCESS, FAILURE, CANCEL, SETUP_NEEDED
	from openid.store.memstore import MemoryStore
	
	consumer = Consumer(request.session, MemoryStore())
	
	ret = consumer.complete(request.REQUEST, original_callback)
	if ret.status != SUCCESS:
		return None
	
	# this should get email but doesn't
	profile = { "id": ret.identity_url }
	
	ax = ret.extensionResponse("http://openid.net/srv/ax/1.0", False)
	for k in ax:
		if k[0:5] == "type.":
			if ax[k] == "http://schema.openid.net/contact/email":
				profile[k[5:]] = ax["value." + k[5:]]
	
	return provider, ret.identity_url, profile

def create_oauth1_client(provider, access_token, verifier = None):
	consumer = oauth.Consumer(providers[provider]["oauth_token"], providers[provider]["oauth_token_secret"])
	token = oauth.Token(access_token['oauth_token'], access_token['oauth_token_secret'])
	if verifier != None:
		token.set_verifier(verifier)
	return oauth.Client(consumer, token)

# The next two functions are based on:
# http://github.com/simplegeo/python-oauth2#readme

def oauth1_get_redirect(request, provider, callback, scope, mode):
	"""Gets the URL for the redirect that begins the OAuth 1 authentication process."""
	consumer = oauth.Consumer(providers[provider]["oauth_token"], providers[provider]["oauth_token_secret"])
	client = oauth.Client(consumer)
	
	body = { "oauth_callback": callback }
	if "additional_request_parameters" in providers[provider]:
		body.update(providers[provider]["additional_request_parameters"])
		if scope != None:
			if "scope" in body:
				body["scope"] += "," + scope
			else:
				body["scope"] = scope

	resp, content = client.request(providers[provider]["request_token_url"], "POST", body= urllib.urlencode(body))
	
	if resp['status'] != '200':
		raise Exception("OAuth1 Failed: Invalid response from " + providers[provider]["displayname"] + " on obtaining a request token: " + content)
	
	request.session["oauth_request_token"] = dict(urlparse.parse_qsl(content))
	request.session["oauth_request_token"]["provider"] = provider
	
	url = providers[provider]["authenticate_url"] + "?" + urllib.urlencode(
		{
			"oauth_token": request.session['oauth_request_token']['oauth_token'],
		})
	
	return url
	
def oauth1_finish_authentication(request, provider, original_callback):
	"""Finishes the authentication for OAuth1. Raises an Exception if the authentication had an error, or otherwise returns a tuple (provider, profile) where provider is the provider id (e.g. "twitter") that started the authentication and profile is a dict returned by the provider that has profile information about the user."""
	if "oauth_problem" in request.GET:
		if request.GET["oauth_problem"] in ("permission_denied", "user_refused"):
			raise UserCancelledAuthentication()
		raise Exception("OAuth1 Failed: "  + request.GET["oauth_problem"])

	provider = request.session['oauth_request_token']['provider']
	client = create_oauth1_client(provider, request.session['oauth_request_token'], request.GET["oauth_verifier"])
	
	resp, content = client.request(providers[provider]["access_token_url"], "GET")
	if resp['status'] != '200':
		raise Exception("OAuth1 Failed: Invalid response from " + providers[provider]["displayname"] + " on obtaining an access token: " + content)

	access_token = dict(urlparse.parse_qsl(content))
	profile = providers[provider]["load_profile"](access_token)
	
	return (provider, access_token, profile)


# The next two functions are based on Facebook's documentation.

def oauth2_get_redirect(request, provider, callback, scope, mode):
	"""Gets the URL for the redirect that begins the OAuth 2 authentication process."""
	
	body = {
			"client_id": providers[provider]["clientid"],
			"redirect_uri": callback,
		}
	if "additional_request_parameters" in providers[provider]:
		body.update(providers[provider]["additional_request_parameters"])
		if scope != None:
			if "scope" in body:
				body["scope"] += "," + scope
			else:
				body["scope"] = scope
	
	if mode == "compact":
		body["display"] = "touch" # works in Facebook
	
	url = providers[provider]["authenticate_url"] + "?" + urllib.urlencode(body)
	return url
	
def oauth2_finish_authentication(request, provider, original_callback):
	"""Finishes the authentication for OAuth2. Raises an Exception if the authentication had an error, or otherwise returns a tuple (provider, access_tok, profile) where provider is the provider id (e.g. "twitter") that started the authentication and profile is a dict returned by the provider that has profile information about the user."""

	if "error_reason" in request.GET:
		if request.GET["error_reason"] == "user_denied":
			raise UserCancelledAuthentication()
		if "error_description" in request.GET:
			raise Exception("OAuth2 Failed: "  + request.GET["error_description"])
		else:
			raise Exception("OAuth2 Failed: "  + request.GET["error_reason"])
	
	url = providers[provider]["access_token_url"] + "?" + urllib.urlencode({
			"client_id": providers[provider]["clientid"],
			"redirect_uri": original_callback,
			"client_secret": providers[provider]["clientsecret"],
			"code": request.GET["code"]
		})
	
	ret = urllib.urlopen(url)
	if ret.getcode() != 200:
		raise Exception("OAuth2 Failed: Invalid response from " + providers[provider]["displayname"] + " on obtaining an access token: " + ret.read())
	ret = ret.read()

	access_token = dict(urlparse.parse_qsl(ret))
	profile = providers[provider]["load_profile"](access_token)
	
	return (provider, access_token, profile)

methods = {
	"openid2": {
		"get_redirect": openid2_get_redirect,
		"finish_authentication": openid2_finish_authentication,
		},
	"oauth1": {
		"get_redirect": oauth1_get_redirect,
		"finish_authentication": oauth1_finish_authentication,
		},
	"oauth2": {
		"get_redirect": oauth2_get_redirect,
		"finish_authentication": oauth2_finish_authentication,
		},
}


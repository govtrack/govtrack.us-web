from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from optparse import make_option

import sys, re, urlparse, urllib

class AppURLopener(urllib.FancyURLopener):
	version = "GovTrack.us scraper" # else Wikipedia gives 403s
urllib._urlopener = AppURLopener()

class Command(BaseCommand):
	args = 'graphid message'
	help = 'Posts a message to a Facebook page stream.'
	
	def handle(self, *args, **options):
		if len(args) != 2:
			print "Missing arguments."
			return

		# Get an access token.
		ret = urllib.urlopen("https://graph.facebook.com/oauth/access_token?" + 
			urllib.urlencode({
			"grant_type": "client_credentials",
			"client_id": settings.FACEBOOK_APP_ID,
			"client_secret": settings.FACEBOOK_APP_SECRET,
		})).read()
		try:
			access_token = urlparse.parse_qs(ret)['access_token'][0]
		except:
			print ret
			return
			
		# Publish to stream.
		print urllib.urlopen("https://graph.facebook.com/%s/feed" % args[0], 
			urllib.urlencode({
			"message": args[1],
			"access_token": access_token,
		})).read()
 
 		

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from django.conf import settings

from optparse import make_option
import sys

from events.models import *

class Command(BaseCommand):
	args = 'feed_name [feed_name ...]'
	help = 'Prints the email addresses of users subscribed to one or more feeds.'
	
	def handle(self, *args, **options):
		if len(args) < 1:
			print "Specify a feed name."
			return
			
		# Get the feeds, and expand to include any contained feeds.
		feeds = [Feed.from_name(arg) for arg in args]
		feeds, map_to_source = expand_feeds(feeds)

		for feed in feeds:
			sys.stderr.write(feed.title + "\n")

		# Get the users tracking any of those feeds.
		users = list(User.objects.filter(
			userprofile__massemail=True,
			subscription_lists__trackers__in=feeds
			).distinct().values_list("email", flat=True))

		# Prints
		users.sort()
		for user in users:
			print user

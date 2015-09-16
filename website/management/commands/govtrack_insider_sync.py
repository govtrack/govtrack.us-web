# sync posts from Medium

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from events.models import Feed
from website.models import MediumPost

class Command(BaseCommand):
	args = ''
	help = 'Syncs GovTrack Insider posts from Medium.'
	
	def handle(self, *args, **options):
		# Ensure feed object exists the first time.
		Feed.objects.get_or_create(feedname="misc:govtrackinsider")

		# Sync.
		MediumPost.sync()
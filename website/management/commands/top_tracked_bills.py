from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db.models import Count

from events.models import Feed
from bill.models import Bill

import datetime

class Command(BaseCommand):
	args = ''
	help = 'Reports top-tracked bills.'
	
	def handle(self, *args, **options):
		print "tracked by users registered in the last two weeks"
		self.show_stats(True)

		print
		print "tracked by all users"
		self.show_stats(False)
	
	def show_stats(self, recent_users_only):
		# get feeds, across all congresses
		top_bills = Feed.objects\
			.filter(feedname__startswith='bill:')\
			.filter(feedname__regex='^bill:[hs][jcr]?%d-' % settings.CURRENT_CONGRESS)
		if recent_users_only:
			top_bills = top_bills.filter(tracked_in_lists__user__date_joined__gt=datetime.datetime.now()-datetime.timedelta(days=14))
		top_bills = top_bills\
			.annotate(count=Count('tracked_in_lists'))\
			.order_by('-count')\
			.values('feedname', 'count')\
			[0:25]

		print "users \t url \t bill title"
		for bf in top_bills:
			b = Bill.from_feed(Feed.from_name(bf["feedname"]))
			print bf["count"], "\t", b.get_absolute_url(), "\t", b
			

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db.models import Count

from events.models import Feed
from bill.models import Bill

class Command(BaseCommand):
	args = ''
	help = 'Reports top-tracked bills.'
	
	def handle(self, *args, **options):
		# get feeds, across all congresses
		top_bills = Feed.objects.annotate(count=Count('tracked_in_lists'))\
			.filter(feedname__startswith='bill:')\
			.filter(feedname__regex='^bill:[hs][jcr]?%d-' % settings.CURRENT_CONGRESS)\
			.order_by('-count')\
			.values('feedname', 'count')\
			[0:25]

		print "users \t url \t bill title"
		for bf in top_bills:
			b = Feed.from_name(bf["feedname"]).bill()
			print bf["count"], "\t", b.get_absolute_url(), "\t", b
			

import shelve

from django.db.models import F
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from person.models import Person

import rtyaml

class Command(BaseCommand):
	help = 'Reports if any legislator twitter bios change.'

	storage_fn = 'data/misc/twitter_bios.shelf'

	def handle(self, *args, **options):
		from website.util import twitter_api_client
		tweepy_client = twitter_api_client()

		screen_names = list(Person.objects.exclude(twitterid=None)
			.values_list("twitterid", "id"))
		twitter_id_to_govtrack_id = dict((s.lower(), g) for (s, g) in screen_names)

		with shelve.open(self.storage_fn) as data:
			while len(screen_names) > 0:
				# Take a batch.
				batch = screen_names[:100]
				screen_names[:len(batch)] = []
				for profile in tweepy_client.lookup_users(screen_names=[b[0] for b in batch]):
					id = str(twitter_id_to_govtrack_id[profile.screen_name.lower()])
					profile = rtyaml.dump({
						"govtrack_id": id,
						"id": profile.id,
						"screen_name": profile.screen_name,
						"name": profile.name,
						"description": profile.description,
						"location": profile.location,
						"entities": profile.entities,
						"verified": profile.verified,
					})

					if id not in data or data[id] != profile:
						print(profile)
						print()

					data[id] = profile

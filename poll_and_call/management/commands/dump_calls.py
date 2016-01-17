from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db.models import Max

import csv, sys
from random import shuffle

from website.models import UserProfile
from poll_and_call.models import *
from person.name import get_person_name

# cache
max_research_anon_key = UserProfile.objects.aggregate(n=Max('research_anon_key'))['n'] or 0

class Command(BaseCommand):
	
	def handle(self, *args, **options):
		# get all calls
		calls = list(CallLog.objects.all()
			.filter(position__position__issue__bills__id__gt=0)	# only calls on bills, since we had a few non-bill calls at the beginning
			.exclude(user__email__endswith="@govtrack.us").exclude(user__email__endswith="@occams.info") # no testing calls by me
			.order_by('created')
			)

		# filter - take only calls with recordings
		calls = filter(lambda call : call.log.get("finished", {}).get("RecordingUrl"), calls)

		## shuffle so new anonymous ID assignments are random
		#shuffle(calls)

		# write out
		w = csv.writer(sys.stdout)

		w.writerow([
			"call_id",
			"call_date",
			"call_duration",
			# "recording_url", # !!! not-anonymized

			"caller_id",
			"caller_account_created",

			"caller_district",
			"caller_areacode",
			"caller_areacode_city",
			"caller_areacode_state",

			"topic_id",
			"topic_name",
			"topic_link",
			"position_id",
			"position_name",

			"office_id",
			"office_type",
			"office_name",
		])

		def anonymize_user(user):
			global max_research_anon_key
			profile = user.userprofile()
			if profile.research_anon_key is None:
				# assign next available ID
				max_research_anon_key += 1
				profile.research_anon_key = max_research_anon_key
				profile.save()
			return profile.research_anon_key

		for call in calls:
			if len(call.position.district) == 2: continue # data error in our very early data (one record?)

			# for making the right name for the called office
			call.target.person.role = call.target

			# write row
			w.writerow([
				# call
				call.id,
				call.created.isoformat(),
				int(call.log["finished"]["RecordingDuration"][0]),
				# !!! this is not anonymous - call.log["finished"]["RecordingUrl"][0],

				# user
				anonymize_user(call.user),
				call.user.date_joined.isoformat(),

				# caller
				call.position.district,
				call.log["start"]["Called"][0][2:5],
				call.log["start"]["CalledCity"][0],
				call.log["start"]["CalledState"][0],

				# topic of call
				call.position.position.issue.first().id,
				call.position.position.issue.first().title.encode("utf8"),
				";".join(["https://www.govtrack.us"+b.bill.get_absolute_url() for b in call.position.position.issue.first().bills.all()]),
				call.position.position.id,
				call.position.position.text.encode("utf8"),

				# target of call
				call.target.person.id,
				call.target.get_title(),
				get_person_name(call.target.person).encode("utf8"),
			])

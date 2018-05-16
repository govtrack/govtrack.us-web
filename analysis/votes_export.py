#!script
import csv, sys

from django.conf import settings

from vote.models import *

with_voters = False

w = csv.writer(sys.stdout)
w.writerow(
	["congress", "session", "chamber", "number", "date", "category", "question", "link"]
	+ (["person", "vote"] if with_voters else [])
)

votes = Vote.objects.filter(
	#congress=113,
	session__in=(2015, 2017),
	chamber=CongressChamber.senate
	).order_by('created')

for vote in votes:
	if with_voters:
		voters = list(vote.voters.all().select_related('person', 'option'))
		voters = sorted(voters, key = lambda v : v.person.sortname)
	else:
		voters = [None]

	for voter in voters:
		row = [
				vote.congress,
				vote.session,
				vote.get_chamber_display(),
				vote.number,
				vote.created.strftime("%x %X"),
				vote.get_category_display(),
				vote.question,
				settings.SITE_ROOT_URL + vote.get_absolute_url(),
			] + ([
				voter.person.sortname,
				voter.option.value,
			] if with_voters else [])
		w.writerow([unicode(v).encode("utf8") for v in row])

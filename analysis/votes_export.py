#!script
import csv, sys

from django.conf import settings

from person.models import Person
from vote.models import Vote, CongressChamber

with_voters = True

w = csv.writer(sys.stdout)
w.writerow(
	["congress", "session", "chamber", "number", "date", "category", "question", "link"]
	+ (["person", "name", "vote"] if with_voters else [])
)

votes = Vote.objects.filter(
	congress=118,
	#session__in=(2015, 2017),
	chamber=CongressChamber.house
	).order_by('created')

for vote in votes:
	if with_voters:
		voters = vote.voters.all()
		voters = list(voters.select_related('person', 'option'))
		voters = sorted(voters, key = lambda v : v.person.sortname_strxfrm)
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
				voter.person.id,
				voter.person.sortname,
				voter.option.value,
			] if with_voters else [])
		w.writerow(row)

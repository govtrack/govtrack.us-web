#!script
import csv, sys

from django.conf import settings

from person.models import Person
from vote.models import Vote

with_voters = False

w = csv.writer(sys.stdout)
w.writerow(
	["congress", "session", "chamber", "number", "date", "category", "question", "link"]
	+ (["person", "vote"] if with_voters else [])
)

#votes = Vote.objects.filter(
#	#congress=113,
#	session__in=(2015, 2017),
#	chamber=CongressChamber.senate
#	).order_by('created')

with_voters = True
people = set(Person.objects.filter(roles__current=True, roles__state="TX"))
votes = Vote.objects.filter(voters__person__in=people).distinct()

for vote in votes:
	if with_voters:
		voters = vote.voters.all()
		if people: voters = voters.filter(person__in=people)
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
				voter.person.sortname,
				voter.option.value,
			] if with_voters else [])
		w.writerow([str(v).encode("utf8") for v in row])

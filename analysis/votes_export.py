#!script
import csv, sys

from django.conf import settings

from vote.models import *
from person.util import load_roles_at_date

w = csv.writer(sys.stdout)
w.writerow([
	"congress", "session", "number", "date", "question", "link", "person", "vote"
])
for vote in Vote.objects.filter(congress=113, chamber=CongressChamber.house).order_by('created'):
	voters = list(vote.voters.all().select_related('person', 'option'))
	voters = sorted(voters, key = lambda v : v.person.sortname)
	load_roles_at_date([x.person for x in voters if x.person != None], vote.created)
	for voter in voters:
		if voter.person.role.state != "AZ": continue
		row = [
				vote.congress,
				vote.session,
				vote.number,
				vote.created.strftime("%x %X"),
				vote.question,
				settings.SITE_ROOT_URL + vote.get_absolute_url(),
				voter.person.sortname,
				voter.option.value,
			]
		w.writerow([unicode(v).encode("utf8") for v in row])

#!script

# Find bills that at least two or more of the specified Members sponsored together.

import sys, csv

from bill.models import *
from person.models import *

# Pass person IDs on the command line.
people = [Person.objects.get(id=id) for id in sys.argv[1:]]

# Write header.
writer = csv.writer(sys.stdout)
headers = ['bill number', 'bill title', 'num cosponsors', 'status', 'link'] + [p1.name for p1 in people]
writer.writerow(headers)

# Find bills that at least one of is the sponsor or cosponsor of.
for bill in (Bill.objects.filter(sponsor__in=people) | Bill.objects.filter(cosponsor__in=people)).distinct():
	row = [bill.display_number, bill.title_no_number, bill.cosponsors.count(), bill.get_current_status_display(), "https://www.govtrack.us" + bill.get_absolute_url()]
	num = 0
	for p in people:
		if bill.sponsor == p:
			row.append("sponsor")
			num += 1
		elif p in bill.cosponsors.all():
			row.append("cosponsor")
			num += 1
		else:
			row.append("")
	if num > 1:
		writer.writerow(row)

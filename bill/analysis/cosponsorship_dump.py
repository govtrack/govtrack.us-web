#!script

import sys, csv

from bill.models import Cosponsor

w = csv.writer(sys.stdout)
w.writerow([
	"joined",
	"withdrawn",
	"bill_id",
	"bill_intro_date",
	"bill_title",
	"bill_link",
	"cosponsor_id",
	"cosponsor_name",
	"cosponsor_link",
	"cosponsor_party",
	"sponsor_id",
	"sponsor_name",
	"sponsor_link",
	"sponsor_party",
])

for c in Cosponsor.objects\
	.filter(bill__congress__gte=113)\
	.order_by('joined', 'bill')\
	.select_related("person", "role", "bill")\
	:
	w.writerow([
		c.joined.isoformat(),
		c.withdrawn.isoformat() if c.withdrawn else "",
		c.bill.id,
		c.bill.introduced_date.isoformat(),
		c.bill.title.encode("utf8"),
		"https://www.govtrack.us" + c.bill.get_absolute_url(),
		c.person.id,
		str(c.person).encode("utf8"),
		"https://www.govtrack.us" + c.person.get_absolute_url(),
		c.role.party,
		c.bill.sponsor.id if c.bill.sponsor else "",
		str(c.bill.sponsor).encode("utf8") if c.bill.sponsor else "",
		("https://www.govtrack.us" + c.bill.sponsor.get_absolute_url()) if c.bill.sponsor else "",
		c.bill.sponsor_role.party if c.bill.sponsor else "",
	])

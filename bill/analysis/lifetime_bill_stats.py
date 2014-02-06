#!script

import sys, csv, datetime

from bill.models import *
from person.models import *

today = datetime.datetime.now().date()

w = csv.writer(sys.stdout)

w.writerow(["est start", "years served", "name", "introduced", "reported", "enacted", "url"])

def get_first_swearing_in_date(r):
	return PersonRole.objects.filter(person=r.person, role_type=r.role_type).order_by("startdate")[0].startdate

def get_number_of_years_served(r):
	years = 0.0
	for r in PersonRole.objects.filter(person=r.person, role_type=r.role_type):
		years += (min(r.enddate, today) - r.startdate).total_seconds() / 60 / 60 / 24 / 365.25
	return years

cur_roles = list(PersonRole.objects.filter(current=True, role_type=RoleType.representative).select_related("person"))
cur_roles.sort(key = lambda r : -get_number_of_years_served(r))

for r in cur_roles:
	row = [
		get_first_swearing_in_date(r).strftime("%x"),
		str(int(round(get_number_of_years_served(r)))),
		unicode(r.person).encode("utf8"),
	]

	# bills introduced
	bills = list(Bill.objects.filter(sponsor=r.person))
	row.append(str(len(bills)))

	# bills reported
	bills_reported = [b for b in bills if b.current_status not in (BillStatus.introduced, BillStatus.referred)]
	row.append(str(len(bills_reported)))

	# bills enacted
	bills_enacted = [b for b in bills if b.was_enacted_ex() is not None]
	row.append(str(len(bills_enacted)))

	row.append("http://www.govtrack.us" + r.person.get_absolute_url())

	w.writerow(row)

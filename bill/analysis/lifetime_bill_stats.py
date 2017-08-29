#!script

# D = read.table("lifetime_bill_stats.csv", header=T, sep=',', quote='"')
# d = D[D$years<=30,]
# model <- lm(d$enacted ~ d$years + d$years:d$party - 1)
# summary(model)
# d$residuals <- model$residuals
# d$fitted.values <- model$fitted.values
# d[order(d$residuals),][0:5,]
# d[order(d$residuals),][(nrow(d)-4):nrow(d),]


import sys, csv, datetime

from bill.models import *
from person.models import *

today = datetime.datetime.now().date()

w = csv.writer(sys.stdout)

w.writerow([
	"est start", "years served",
	"# introduced", "# reported", "# enacted",
	"name", "current party", "link"
	])

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
		str(round(get_number_of_years_served(r), 1)),
	]

	# bills introduced
	bills = Bill.objects.filter(sponsor=r.person)
	#bills = bills.filter(introduced_date__gt="1993-01-05")
	bills = list(bills)
	row.append(str(len(bills)))

	# bills reported
	bills_reported = [b for b in bills if b.current_status != BillStatus.introduced]
	row.append(str(len(bills_reported)))

	# bills enacted
	bills_enacted = [b for b in bills if b.was_enacted_ex() is not None]
	row.append(str(len(bills_enacted)))

	row.extend([
		unicode(r.person).encode("utf8"),
		r.party,
		"http://www.govtrack.us" + r.person.get_absolute_url(),
	])

	w.writerow(row)

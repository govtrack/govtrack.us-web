#!script

from datetime import datetime, timedelta
import csv, sys

from django.db.models import Count

from us import get_congress_dates
from settings import CURRENT_CONGRESS

from bill.models import Bill, BillStatus
from bill.billtext import load_bill_text
from vote.models import Vote, CongressChamber
from person.models import PersonRole, RoleType

W = csv.writer(sys.stdout)
W.writerow(["congress", "congress years", "date_start", "date_end", "enacted bills", "enacted pages", "enacted words", "house votes", "senate votes"])

def compute_productivity(congress, date_range):
	# laws

	enacted_bills = Bill.objects.filter(
		congress=congress, # if we're measuring presidential activity, the date of signing could be outside of the Congress, so change this

		current_status__in=BillStatus.final_status_enacted_bill,
		#current_status=BillStatus.enacted_signed,
		current_status_date__gte=date_range[0],
		current_status_date__lte=date_range[1]

		#introduced_date__gte=date_range[0],
		#introduced_date__lte=date_range[1]

		)\
		.order_by('current_status_date')

	if date_range[0].month == 1 and date_range[0].day == 20:
		# last bill Obama signed was a rare Jan 20th morning
		enacted_bills = enacted_bills.exclude(id=347731)

	#enacted_bills = (enacted_bills.filter(title__contains="Appropriations") | enacted_bills.filter(title__contains="Authorization")).distinct()

	enacted_bills = list(enacted_bills)
	enacted_bills_count = len(enacted_bills)

	enacted_bill_pages = 0
	enacted_bill_words = 0
	enacted_bill_pages_missing = 0
	for b in enacted_bills:
		try:
			pp = load_bill_text(b, None, mods_only=True).get("numpages")
		except IOError:
			pp = None
		if pp is None:
			enacted_bill_pages_missing += 1
			continue
		pp = int(pp.replace(" pages", ""))
		enacted_bill_pages += pp

		wds = len(load_bill_text(b, None, plain_text=True).split(" "))
		enacted_bill_words += wds

 	if congress < 103: enacted_bill_pages = "(no data)"
 	if congress < 103: enacted_bill_words = "(no data)"

	# votes

	house_votes = Vote.objects.filter(
		congress=congress,
		created__gte=date_range[0],
		created__lte=date_range[1],
		chamber=CongressChamber.house).count()
	senate_votes = Vote.objects.filter(
		congress=congress,
		created__gte=date_range[0],
		created__lte=date_range[1],
		chamber=CongressChamber.senate).count()

	timespan = "%d-%d" % (get_congress_dates(congress)[0].year, ((get_congress_dates(congress)[1].year-1) if get_congress_dates(congress)[1].month == 1 else get_congress_dates(congress)[1].year))
	row = [congress, timespan, date_range[0].isoformat(), date_range[1].isoformat(),
		enacted_bills_count, enacted_bill_pages, enacted_bill_words, house_votes, senate_votes]
	W.writerow(row)
	#print("<tr>%s</tr>" % "".join( "<td>%s</td> " % td for td in row) )

if 0:
	# Look at corresponding time periods from past Congresses.
	# Go back a few days because our data isn't real time!
	days_in = (datetime.now().date() - get_congress_dates(CURRENT_CONGRESS)[0]) \
		- timedelta(days=4)
	print("We are about %d days into the %d Congress" % (days_in.days, CURRENT_CONGRESS))
	for c in range(93, CURRENT_CONGRESS+1):
		date_range = get_congress_dates(c)
		compute_productivity(c, (date_range[0], date_range[0] + days_in))

elif 1:
	# First X days of presidency, minus a few days because of
	# data delays.
	days_in = (datetime.now().date() - datetime(get_congress_dates(CURRENT_CONGRESS)[0].year, 1, 20, 0, 0, 0).date()) \
		- timedelta(days=0)
	#days_in = timedelta(days=150)
	print("We are about %d days into the presidency" % days_in.days)
	for c in (95, 97, 101, 103, 107, 111, 115):
		date_range = get_congress_dates(c)
		date_range = (datetime(date_range[0].year, 1, 20).date(), datetime(date_range[0].year, 1, 20).date()+days_in)
		compute_productivity(c, date_range)

elif 0:
	for c in range(93, CURRENT_CONGRESS+1):
		# First or second session only.
		date_range = get_congress_dates(c)
		date_range = (date_range[0], datetime(date_range[0].year, 12, 31).date())
		#date_range = (datetime(date_range[0].year+1, 1, 1).date(), date_range[1])
		compute_productivity(c, date_range)

else:
	# Whole Congress.
	for c in range(93, CURRENT_CONGRESS+1):
		date_range = get_congress_dates(c)
		date_range[1] += timedelta(days=20) # 10 day rule for signing, plus buffer
		compute_productivity(c, date_range)

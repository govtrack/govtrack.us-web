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

party_control = { }
for row in csv.reader(open("analysis/party_control.tsv"), delimiter='\t'):
	if row[0].startswith("#") or row[0] == 'Congress': continue
	party_control[int(row[0])] = (row[3], row[9], row[15]) # senate, house, presidency

W = csv.writer(sys.stdout)

def compute_productivity(congress, days_in):
	corresponding_day = get_congress_dates(congress)[0] + days_in

	# laws

	enacted_bills = list(Bill.objects.filter(
		congress=congress,
		current_status__in=BillStatus.final_status_passed_bill,
		current_status_date__lte=corresponding_day))
	enacted_bills_count = len(enacted_bills)

	enacted_bill_pages = 0
	enacted_bill_words = 0
	enacted_bill_pages_missing = 0
	for b in enacted_bills:
		pp = load_bill_text(b, None, mods_only=True).get("numpages")
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
		created__lte=corresponding_day,
		chamber=CongressChamber.house).count()
	senate_votes = Vote.objects.filter(
		congress=congress,
		created__lte=corresponding_day,
		chamber=CongressChamber.senate).count()

	# power

	congress_same_party = party_control[congress][0] == party_control[congress][1]
	branches_same_party = (party_control[congress][0] == party_control[congress][1]) and (party_control[congress][0] == party_control[congress][2])

	#

	timespan = "%d (%d-%d)" % (congress, get_congress_dates(congress)[0].year, get_congress_dates(congress)[1].year-1)
	row = [timespan, enacted_bills_count, enacted_bill_pages, enacted_bill_words, house_votes, senate_votes, "Yes" if congress_same_party else "No", "Yes" if branches_same_party else "No"]
	#W.writerow(row)
	print("<tr>%s</tr>" % "".join( "<td>%s</td> " % td for td in row) )


#days_in = (datetime.now().date() - get_congress_dates(CURRENT_CONGRESS)[0])
#print("We are %d days into the %d Congress" % (days_in.days, CURRENT_CONGRESS))
days_in = timedelta(days=506)
print("Using %s days." % days_in)

for c in range(93, 113+1):
	compute_productivity(c, days_in)

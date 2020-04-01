#!script

import sys, csv
from collections import defaultdict

from django.db.models import Count

from settings import CURRENT_CONGRESS

from bill.models import Bill, BillStatus
from bill.billtext import load_bill_text

from us import get_congress_years

from numpy import median

W = csv.writer(sys.stdout)
W.writerow([
	"congress",
	"years",
	"bills",
	"pages",
	"words",
	"median pages per bill",
	"median words per bill",
	"bills_with_missing_text",
])

def count_pages_of_bills(congress):
	counters = defaultdict(lambda : [])
	missing_text = 0

	qs = Bill.objects.filter(congress=congress)\
		.filter(current_status__in=BillStatus.final_status_enacted_bill)
	for b in qs:
		plain_text = load_bill_text(b, None, plain_text=True)

		if congress >= 103:
			# Bills since 1993 have GPO MODS XML metadata with page counts.
			try:
				pp = load_bill_text(b, None, mods_only=True).get("numpages")
			except IOError:
				missing_text += 1
				continue
			if pp is None:
				missing_text += 1
				continue
		else:
			# For historical statutes we only have plain text from the
			# Statutes at Large, extracted from PDFs. We can get page
			# counts by looking for our replacement of the form feed
			# character put in by pdftotext. We only have that when
			# we extracted text from PDFs, which we only did for
			# the Statutes at Large. We can't do this on modern bills
			# where the text came from GPO plain text format.
			pp = len([pgtext for pgtext in plain_text.split("\n=============================================\n") if pgtext.strip() != ""])

		wds = len(plain_text.split(" "))

		counters["pages"].append(pp)
		counters["words"].append(wds)

	W.writerow([congress, "{}-{}".format(*get_congress_years(congress)),
		len(counters["pages"]), sum(counters["pages"]), sum(counters["words"]),
		int(round(median(counters["pages"]))), int(round(median(counters["words"]))),
		missing_text])

for c in range(82, CURRENT_CONGRESS+1):
	count_pages_of_bills(c)

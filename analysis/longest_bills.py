#!script

import sys, csv
from tqdm import tqdm

from django.db.models import Count

from settings import CURRENT_CONGRESS

from bill.models import Bill, BillStatus
from bill.billtext import load_bill_text


W = csv.writer(sys.stdout)
W.writerow([
	"congress",
	"date",
	"bill",
	"pages",
	"words",
])

def count_pages_of_bills(congress):
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

		W.writerow([congress, b.current_status_date.isoformat(),
			b.get_absolute_url(), pp, wds]),

for c in tqdm(range(82, CURRENT_CONGRESS+1)):
	count_pages_of_bills(c)

#!script

from datetime import datetime, timedelta
import csv, sys, re

from us import get_congress_dates

from bill.models import Bill, BillStatus
from bill.billtext import load_bill_text

import tqdm

def run_analysis_for_president(president, date_range):
	global stats
	global columns

	start_date = datetime.strptime(date_range[0], "%Y-%m-%d").date()
	end_date = datetime.strptime(date_range[1], "%Y-%m-%d").date()

	# limit to first year
	end_date = min(start_date+timedelta(days=365), end_date)

	# if we're measuring presidential activity, the date of signing could be outside of the Congress
	enacted_bills = Bill.objects.filter(
		current_status__in=BillStatus.final_status_enacted_bill,
		sliplawpubpriv="PUB", # questionable
		current_status_date__gte=start_date,
		current_status_date__lte=end_date
		)\
		.order_by('current_status_date')

	# last bill Obama signed was a rare Jan 20th morning
	enacted_bills = enacted_bills.exclude(id=347731)

	by_day = { }
	for b in tqdm.tqdm(enacted_bills, desc=president):
		# Load plain text.
		text = load_bill_text(b, None, plain_text=True)

		# Bills since 1993 have GPO MODS XML metadata with page counts.
		try:
			mods = load_bill_text(b, None, mods_only=True)
			pages = int(mods.get("numpages").replace(" pages", ""))
		except (IOError, AttributeError) as e:
			# For historical statutes we only have plain text from the
			# Statutes at Large, extracted from PDFs. We can get page
			# counts by looking for our replacement of the form feed
			# character put in by pdftotext. We only have that when
			# we extracted text from PDFs, which we only did for
			# the Statutes at Large. We can't do this on modern bills
			# where the text came from GPO plain text format.
			if b.congress < 103:
				pages = len(text.split("\n=============================================\n"))
			else:
				print b.id, b, e
				raise ValueError("page date missing")

		words = len(re.split(r"\s+", text))

		rel_date = (b.current_status_date - start_date).days
		rec = by_day.setdefault(rel_date, { "bills": 0, "pages": 0, "words": 0 } )
		rec["bills"] += 1
		rec["pages"] += pages
		rec["words"] += words

	# Compute cumulative counts starting on day 0 and for every day till the
	# last day a bill was signed.
	columns.append(president)
	bills = 0
	pages = 0
	words = 0
	for rel_date in range(max(by_day)+1):
		if rel_date in by_day:
			bills += by_day[rel_date]["bills"]
			pages += by_day[rel_date]["pages"]
			words += by_day[rel_date]["words"]
		stats.setdefault(rel_date, {})[president] = (bills, pages, words)

# Collect data

stats = { }
columns = []

run_analysis_for_president("Eisenhower", ("1953-01-20","1961-01-19"))
run_analysis_for_president("Kennedy", ("1961-01-20","1963-11-22"))
run_analysis_for_president("Nixon", ("1969-01-20","1974-08-09"))
run_analysis_for_president("Carter", ("1977-01-20","1981-01-19"))
run_analysis_for_president("Reagan", ("1981-01-20","1989-01-19"))
run_analysis_for_president("Bush1", ("1989-01-20","1993-01-19"))
run_analysis_for_president("Clinton", ("1993-01-20","2001-01-19"))
run_analysis_for_president("Bush2", ("2001-01-20","2009-01-19"))
run_analysis_for_president("Obama", ("2009-01-20","2017-01-19"))
run_analysis_for_president("Trump", ("2017-01-20","2018-01-19"))

# Write out.

W = csv.writer(sys.stdout)
W.writerow(["reldate", "date"] + sum(([president, "pages", "words"] for president in columns), []))
day_zero = datetime.strptime("2017-01-20", "%Y-%m-%d").date()
for rel_date in range(max(stats)+1):
	W.writerow(
		[ rel_date, (day_zero+timedelta(days=rel_date)).strftime("%m-%d") ]
		+ sum(
			(
				list(stats[rel_date][president])
				if president in stats[rel_date]
				else ["", "", ""]
				for president in columns
			), [])
	)


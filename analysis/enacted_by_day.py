#!script

from datetime import datetime, timedelta
import csv, sys, os, re

from us import get_congress_dates

from bill.models import Bill, BillStatus
from bill.billtext import load_bill_text

import tqdm

def run_analysis_for_president(president, date_range):
	global stats
	global columns

	start_date = datetime.strptime(date_range[0], "%Y-%m-%d").date()
	end_date = datetime.strptime(date_range[1], "%Y-%m-%d").date()

	# limit to now, for the current president
	end_date = min(end_date, datetime.now().date())

	# limit to a shorter period than a whole presidency so this computes faster
	#end_date = min(start_date+timedelta(days=365*2.5), end_date)

	# if we're measuring presidential activity, the date of signing could be outside of the Congress
	enacted_bills = Bill.objects.filter(
		current_status__in=BillStatus.final_status_enacted_bill,
		#sliplawpubpriv="PUB", # questionable
		current_status_date__gte=start_date, # only use this if looking at a final status
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
			pages = mods.get("numpages")
			if pages is None: raise IOError() # try another way
		except (IOError, AttributeError) as e:
			# For historical statutes we only have plain text from the
			# Statutes at Large, extracted from PDFs. We can get page
			# counts by looking for our replacement of the form feed
			# character put in by pdftotext. We only have that when
			# we extracted text from PDFs, which we only did for
			# the Statutes at Large. We can't do this on modern bills
			# where the text came from GPO plain text format.
			if b.congress < 103:
				pages = len([pgtext for pgtext in text.split("\n=============================================\n") if pgtext.strip() != ""])
			else:
				print(b.id, b, e)
				raise ValueError("page date missing")

		#words = len(re.split(r"\s+", text)) # not very good for pre-GPO bills because Statutes at Large pages may have multiple statutes on them

		if os.environ.get("PAGES") == "1" and pages > 1: continue
		if os.environ.get("PAGES") == ">1" and pages <= 1: continue

		#if b.congress == 115: print pages, b

		rel_date = (b.current_status_date - start_date).days
		rec = by_day.setdefault(rel_date, { "bills": 0, "pages": 0 } )
		rec["bills"] += 1
		rec["pages"] += pages
		#rec["words"] += words

	# Compute cumulative counts starting on day 0 and for every day till the
	# last day a bill was signed.
	columns.append(president)
	bills = 0
	pages = 0
	#words = 0
	for rel_date in range((end_date-start_date).days+1):
		if rel_date in by_day:
			bills += by_day[rel_date]["bills"]
			pages += by_day[rel_date]["pages"]
			#words += by_day[rel_date]["words"]
		stats.setdefault(rel_date, {})[president] = (bills, pages)

# Collect data

stats = { }
columns = []

# Only presidents whose first term began at the start of a Congress.
run_analysis_for_president("Eisenhower", ("1953-01-20","1961-01-19"))
run_analysis_for_president("Kennedy", ("1961-01-20","1963-11-22"))
run_analysis_for_president("Nixon", ("1969-01-20","1974-08-09"))
run_analysis_for_president("Carter", ("1977-01-20","1981-01-19"))
run_analysis_for_president("Reagan", ("1981-01-20","1989-01-19"))
run_analysis_for_president("Bush 41", ("1989-01-20","1993-01-19"))
run_analysis_for_president("Clinton", ("1993-01-20","2001-01-19"))
run_analysis_for_president("Bush 43", ("2001-01-20","2009-01-19"))
run_analysis_for_president("Obama", ("2009-01-20","2017-01-19"))
run_analysis_for_president("Trump", ("2017-01-20","2021-01-19"))

# Write out.

import re
def fmt_day(d): return re.sub(r"^0", "", d.strftime("%m/%d"))
day_zero = datetime.strptime("2017-01-20", "%Y-%m-%d").date()

W = csv.writer(sys.stdout)

if len(sys.argv) == 1:
	# show all days

	# what to show in each president column
	if os.environ.get("COUNT") == "pages":
		stat_val = lambda day, president : day[president][1] # pages
	elif os.environ.get("RANK"): # "pages" = "count"
		idx = 0 if os.environ.get("RANK") == "count" else 1
		stat_val = lambda day, president : sorted((day[p][idx] for p in columns if p in day), reverse=True).index(day[president][idx]) + 1
	else:
		stat_val = lambda day, president : day[president][0] # count

	W.writerow(["reldate", "date"] + [president for president in columns])
	for rel_date in range(max(stats)+1):
		W.writerow(
			[ (rel_date+1), fmt_day(day_zero+timedelta(days=rel_date)) ]
			+ [
					stat_val(stats[rel_date], president)
					if president in stats[rel_date]
					else ""
					for president in columns
			]
		)
else:
	# show only requested date
	rel_date = int(sys.argv[1])-1
	print(rel_date+1, fmt_day(day_zero+timedelta(days=rel_date)))
	W.writerow(["president", "bills", "pages"])
	for president in columns:
		if president in stats[rel_date]:
			W.writerow([president] + list(stats[rel_date][president]))

#!script

import datetime
import csv, sys, re

from us import get_congress_dates

from bill.models import Bill, BillStatus, BillType
from bill.billtext import load_bill_text

import tqdm

def run_analysis(label, congress):
	global stats
	global columns

	congress_dates = get_congress_dates(congress)

	start_date = datetime.date(congress_dates[0].year, 1, 1)

	# limit to now, for the current congress
	end_date = datetime.date(congress_dates[0].year, 9, 11)
	end_date = min(end_date, datetime.datetime.now().date())

	bills = Bill.objects.filter(congress=congress, bill_type__in=(BillType.house_bill, BillType.senate_bill, BillType.house_joint_resolution, BillType.senate_joint_resolution), introduced_date__lte=end_date)\
		.order_by('current_status_date')
	by_day = { }
	for b in tqdm.tqdm(bills, desc=label):
		match_date = None
		for datestr, state, text, srcxml in b.major_actions:
			action_date = eval(datestr)
			#if state in (BillStatus.pass_over_house, BillStatus.pass_back_house, BillStatus.passed_bill):
			if state in BillStatus.final_status_enacted_bill:
				match_date = action_date.date()
				break
		else:
			# No event matched.
			continue

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
				pages = len([pgtext for pgtext in text.split("\n=============================================\n") if pgtext.strip() != ""])
			else:
				print b.id, b, e
				raise ValueError("page date missing")

		#words = len(re.split(r"\s+", text)) # not very good for pre-GPO bills because Statutes at Large pages may have multiple statutes on them

		################ EEK
		#if pages == 1: continue
		################ EEK

		rel_date = (match_date - start_date).days
		rec = by_day.setdefault(rel_date, { "bills": 0, "pages": 0 } )
		rec["bills"] += 1
		rec["pages"] += pages
		#rec["words"] += words

	# Compute cumulative counts starting on day 0 and for every day till the
	# last day a bill was signed.
	columns.append(label)
	bills = 0
	pages = 0
	#words = 0
	for rel_date in range((end_date-start_date).days+1):
		if rel_date in by_day:
			bills += by_day[rel_date]["bills"]
			pages += by_day[rel_date]["pages"]
			#words += by_day[rel_date]["words"]
		stats.setdefault(rel_date, {})[label] = (bills, pages)

# Collect data

stats = { }
columns = []

run_analysis("97/Reagan", 97)
run_analysis("101/Bush 41", 101)
run_analysis("103/Clinton", 103)
run_analysis("107/Bush 43", 107)
run_analysis("111/Obama", 111)
run_analysis("115/Trump", 115)

# Write out.

import re
def fmt_day(d): return re.sub(r"^0", "", d.strftime("%m/%d"))
day_zero = datetime.datetime.strptime("2017-01-01", "%Y-%m-%d").date()

W = csv.writer(sys.stdout)

if len(sys.argv) == 1:
	# show all days
	W.writerow(["reldate", "date"] + sum(([label, "pages"] for label in columns), []))
	for rel_date in range(max(stats)+1):
		W.writerow(
			[ (rel_date+1), fmt_day(day_zero+datetime.timedelta(days=rel_date)) ]
			+ sum(
				(
					list(stats[rel_date][label])
					if label in stats[rel_date]
					else ["", ""]
					for label in columns
				), [])
		)
else:
	# show only requested date
	rel_date = int(sys.argv[1])-1
	print(rel_date+1, fmt_day(day_zero+datetime.timedelta(days=rel_date)))
	W.writerow(["label", "bills", "pages"])
	for label in columns:
		if label in stats[rel_date]:
			W.writerow([label] + list(stats[rel_date][label]))

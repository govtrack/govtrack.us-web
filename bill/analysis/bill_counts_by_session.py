#!script

import sys, csv, json

from us import get_all_sessions
from bill.models import *
from bill.status import BillStatus
from bill.billtext import load_bill_text

status_names = { }
status_names["MISSING_TEXT"] = "(number of bills that I'm missing text for)"

w = csv.writer(sys.stdout)
w.writerow(["congress", "session", "status code", "status name" "pages"])

for congress, session, startdate, enddate in get_all_sessions():
	# before the 103rd, there's no MODS data
	if congress < 103: continue

	# to get bills in the first session, look for bills that were
	# introduced before the end of the session.
	bills = Bill.objects.filter(
		congress=congress,
		introduced_date__gte=startdate,
		introduced_date__lte=enddate,
		)

	# get page counts by GPO version code
	page_counts = { }
	for b in bills:
		try:
			mods = load_bill_text(b, None, mods_only=True)
		except IOError:
			status = "MISSING_TEXT"
			page_counts[status] = page_counts.get(status, 0) + 1
			continue

		status = mods["doc_version"]
		if status is None or status.strip() == "": status = "UNKNOWN"
		status_names[status] = mods["doc_version_name"]
		pp = int(mods.get("numpages").replace(" pages", ""))
		page_counts[status] = page_counts.get(status, 0) + pp

	for status, page_count in sorted(page_counts.items(), key = lambda kv : -kv[1]):
		w.writerow([str(congress), session, status, status_names[status], str(page_count)])


#!script

import sys, csv, json

from us import get_all_sessions
from bill.models import *
from bill.status import BillStatus
from bill.billtext import load_bill_text

for congress, session, startdate, enddate in get_all_sessions():
	# look at the 1st session of each Congress since the start of bill status data
	if congress < 93: continue
	if int(session) % 2 != 1: continue

	# to get bills in the first session, look for bills that were
	# introduced before the end of the session.
	bills = Bill.objects.filter(
		congress=congress,
		introduced_date__lte=enddate,
		bill_type__in=(BillType.house_bill, BillType.senate_bill, BillType.house_joint_resolution, BillType.senate_joint_resolution),
		)

	# to get enacted bills, check that it was also enacted within
	# the first session because comparing it to the 113th Congress
	# 1st Session today, we don't know what will be enacted in the
	# 2nd Session.
	enacted_bills = set(bills.filter(
		current_status__in=BillStatus.final_status_passed_bill,
		current_status_date__lte=enddate))

	# Our final status ENACTED:* relies on the bill being assigned
	# a slip law number by OFR. This is different from the bill actually
	# being enacted and is certainly different from the popular notion
	# of a bill being signed by the president. Compute the enacted list
	# by looking at <signed> action types.
	for b in bills:
		fn = "data/congress/%s/bills/%s/%s%d/data.json" % (
        	b.congress,
            BillType.by_value(b.bill_type).slug,
            BillType.by_value(b.bill_type).slug,
            b.number)
		bj = json.load(open(fn))
		for axn in bj["actions"]:
			if axn["type"] == "signed" and axn["acted_at"] <= enddate.isoformat():
				enacted_bills.add(b)

	page_count = 0
	if congress >= 103:
		for b in enacted_bills:
			pp = load_bill_text(b, None, mods_only=True).get("numpages")
			pp = int(pp.replace(" pages", ""))
			page_count += pp

	print congress, session, bills.count(), len(enacted_bills), page_count


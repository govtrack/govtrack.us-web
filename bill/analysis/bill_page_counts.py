#!script

import csv, sys

from us import get_all_sessions
from bill.models import *
from bill.billtext import load_bill_text

C = csv.writer(sys.stdout)

for congress, session, startdate, enddate in get_all_sessions():
	if congress < 103: continue

	bills = Bill.objects.filter(
		congress=congress,
		introduced_date__gte=startdate,
		introduced_date__lte=enddate,
		).order_by('introduced_date')

	for b in bills:
		try:
			pp = load_bill_text(b, None, mods_only=True).get("numpages")
			pp = int(pp.replace(" pages", ""))
		except IOError:
			pp = "NA"
		
		C.writerow([b.congress, session, BillType.by_value(b.bill_type).slug, str(b.number), str(pp)])


#!script

import csv, sys, re

from django.db.models import Count

from settings import CURRENT_CONGRESS

from bill.models import Bill, BillStatus, BillType
from bill.billtext import load_bill_text

W = csv.writer(sys.stdout)
for congress in range(CURRENT_CONGRESS, 103-1, -1):
	enacted_bills = Bill.objects.filter(
		bill_type__in=(BillType.senate_bill, BillType.house_bill),
		congress=congress,
		current_status__in=BillStatus.final_status_enacted_bill)

	#enacted_bills = (enacted_bills.filter(title__contains="Appropriations") | enacted_bills.filter(title__contains="Authorization")).distinct()

	enacted_bills = list(enacted_bills)
	enacted_bills_count = len(enacted_bills)

	enacted_bill_cites_usc = 0
	enacted_bill_cites_cfr = 0
	enacted_bill_cites_pl = 0
	for b in enacted_bills:
		metadata = load_bill_text(b, None, mods_only=True)
		cite_types = set()
		for cite in metadata["citations"]:
			cite_types.add(cite["type"])

		text = load_bill_text(b, None, plain_text=True)
		m = re.search("code\s+of\s+federal\s+regulations", text, re.I)
		if m: cite_types.add("cfr")
		m = re.search("\d+ c\.?f\.?r\.?", text, re.I)
		if m: cite_types.add("cfr")

		if "usc-chapter" in cite_types or "usc-section" in cite_types:
			enacted_bill_cites_usc += 1
		if "statutes_at_large" in cite_types or "slip_law" in cite_types:
			enacted_bill_cites_pl += 1
		if "cfr" in cite_types:
			enacted_bill_cites_cfr += 1

	W.writerow([congress, enacted_bills_count,
		int(round(100*enacted_bill_cites_usc/enacted_bills_count)),
		int(round(100*enacted_bill_cites_pl/enacted_bills_count)),
		int(round(100*enacted_bill_cites_cfr/enacted_bills_count)),
	])

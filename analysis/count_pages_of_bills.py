#!script

import sys, tqdm
from collections import defaultdict

from django.db.models import Count

from settings import CURRENT_CONGRESS

from bill.models import Bill, BillStatus
from bill.billtext import load_bill_text

def doit(congress):
	all = defaultdict(lambda : 0)
	enacted = defaultdict(lambda : 0)
	missing_text = 0

	qs = Bill.objects.filter(congress=congress)
	for b in tqdm.tqdm(qs, total=qs.count()):
		try:
			pp = load_bill_text(b, None, mods_only=True).get("numpages")
		except IOError:
			missing_text += 1
			continue
		pp = int(pp.replace(" pages", ""))
		wds = len(load_bill_text(b, None, plain_text=True).split(" "))

		all["count"] += 1
		all["pages"] += pp
		all["words"] += wds
		if b.current_status in BillStatus.final_status_enacted_bill:
			enacted["count"] += 1
			enacted["pages"] += pp
			enacted["words"] += wds


	print congress, all["count"], all["pages"], all["words"], enacted["count"], enacted["pages"], enacted["words"]
	print "\t", missing_text, "missing text"

doit(114)

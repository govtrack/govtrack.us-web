#!script

import os.path
from bill.models import Bill, BillType

all_bill_ids = list(Bill.objects.all().values_list('id', flat=True))

def batch(iterable, n = 1):
   l = len(iterable)
   for ndx in range(0, l, n):
	   yield iterable[ndx:min(ndx+n, l)]

for idset in batch(all_bill_ids, n=2000):
	print "..."
	for bill in Bill.objects.only('congress', 'bill_type', 'number').in_bulk(idset).values():
		fn = "data/congress/%s/bills/%s/%s%d/data.json" % (
			bill.congress,
			BillType.by_value(bill.bill_type).slug,
			BillType.by_value(bill.bill_type).slug,
			bill.number)

		if not os.path.exists(fn):
			print bill.id, bill



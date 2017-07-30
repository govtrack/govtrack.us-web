#!script

import sys, csv
from django.db.models import Count
from bill.models import Cosponsor, Bill, BillType

w = csv.writer(sys.stdout)

csp = Cosponsor.objects\
	.filter(bill__congress=114, bill__bill_type=BillType.senate_bill)\
	.values("bill")\
	.annotate(count=Count("bill"))\
	.order_by('-count')
for rec in csp[0:100]:
	bill = Bill.objects.get(id=rec['bill'])
	w.writerow([
		rec['count'],
		bill.display_number_no_congress_number + ": " + bill.title_no_number.encode("utf8"),
		bill.get_current_status_display().encode("utf8"),
	])


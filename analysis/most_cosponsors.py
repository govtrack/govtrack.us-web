#!script

import sys, csv
from django.db.models import Count
from bill.models import Cosponsor, Bill, BillType

w = csv.writer(sys.stdout)

	#.filter(bill__congress=114, bill__bill_type=BillType.senate_bill)\
csp = Cosponsor.objects\
	.values("bill")\
	.annotate(count=Count("bill"))\
	.filter(count__gte=218)\
	.order_by('-count', '-bill__introduced_date')
for rec in csp:
	bill = Bill.objects.get(id=rec['bill'])
	w.writerow([
		rec['count'],
		#bill.display_number_no_congress_number + ": " + bill.title_no_number.encode("utf8"),
		bill.congressproject_id,
		bill.display_number,
		bill.title_no_number.encode("utf8"),
		bill.get_current_status_display().encode("utf8"),
	])


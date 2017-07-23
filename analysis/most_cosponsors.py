#!script

from django.db.models import Count
from bill.models import Cosponsor, Bill, BillType

csp = Cosponsor.objects\
	.filter(bill__congress=114, bill__bill_type=BillType.senate_bill)\
	.values("bill")\
	.annotate(count=Count("bill"))\
	.order_by('-count')
for rec in csp[0:10]:
	bill = Bill.objects.get(id=rec['bill'])
	print rec['count'], bill.display_number_no_congress_number + ": " + bill.title_no_number


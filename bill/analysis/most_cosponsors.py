#!script

from django.db.models import Count
import sys, csv
from bill.models import Cosponsor, Bill, BillStatus

bills_most_cosponsored = \
	Cosponsor.objects \
 	 .filter(bill__congress=114) \
	 .filter(withdrawn=None) \
	 .values("bill") \
	 .annotate(count=Count('id')) \
	 .order_by("-count") #\
	#[0:200]

w = csv.writer(sys.stdout)
for bill_and_count in bills_most_cosponsored:
	bill = Bill.objects.get(id=bill_and_count["bill"])
	w.writerow([
		bill_and_count["count"],
		unicode(bill).encode("utf8"),
		BillStatus.by_value(bill.current_status).label.encode("utf8"),
		"https://www.govtrack.us" + bill.get_absolute_url(),
	])

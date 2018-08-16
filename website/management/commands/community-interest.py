# Scan the CommunityInterest table for communities we should created.

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db.models import Count

from optparse import make_option

from bill.models import Bill, RelatedBill
from website.models import CommunityInterest

class Command(BaseCommand):
	args = ''
	help = 'Checks the CommunityInterest table for new communities we should created.'
	
	def handle(self, *args, **options):
		# Get counts by bill, and load the bills in bulk.
		interests = list(CommunityInterest.objects.values('bill').annotate(count=Count('id')))
		bills = Bill.objects.in_bulk(ik['bill'] for ik in interests)
		for ix in interests:
			ix["bills"] = set()
			ix["bills"].add(bills[ix["bill"]])
				
		# Combine related bills.
		interest_index = dict((x["bill"], i) for i, x in enumerate(interests))
		for b in bills.values():
			for rb in b.get_related_bills():
				rb = rb.related_bill
				if rb.id in interest_index:
					n = interests[interest_index[rb.id]]
					m = interests[interest_index[b.id]]
					m = m.get("map_to", m)
					if m == n: continue
					n["map_to"] = m
					m["count"] += n["count"]
					m["bills"].add(rb)
					n["count"] = 0
		

		
		print("Top Bills")
		interests.sort(key = lambda ix : ix["count"], reverse=True)
		for i in range(20):
			for b in interests[i]["bills"]:
				print(b)
			print("\t", len(set(CommunityInterest.objects.filter(bill__in=interests[i]["bills"]).values_list("user", flat=True))), "distinct users")
			methods = { }
			for ci in CommunityInterest.objects.filter(bill__in=interests[i]["bills"]):
				for m in ci.methods.split(","):
					methods[m] = methods.get(m, 0) + 1
			print("\t", methods)
			print()

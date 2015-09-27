#!script

from bill.models import *
from datetime import date

for congress in [112]: # range(96, 113):
	total = 0
	has_initial_cosponsors = 0
	bipartisan_cosp = 0
	total_has_companion = 0
	total_companion_bipartisan = 0
	
	for bill in Bill.objects.filter(congress=congress, bill_type__in=(BillType.house_bill, BillType.senate_bill)).select_related("sponsor"):
		#.filter(introduced_date__gte=date(2011, 8, 1)):
		total += 1
		
		# People we care about. Batch load party information for sponsors
		# and cosponsors to be fast. Load roles at the bill introduced date.
		# Only look at cosponsors who joined on the introduced date (otherwise
		# they may have changed party between those two dates).
		persons = []
		if not bill.sponsor: continue
		persons.append(bill.sponsor)
		persons.extend([(c.person, c.person_role) for c in Cosponsor.objects.filter(bill=bill, joined=bill.introduced_date).select_related("person", "person_role")])
		
		if len(persons) > 1: has_initial_cosponsors += 1
		
		# How bipartisan_cosp is this bill?
		parties = set()
		for p, r in persons:
			if r:
				parties.add(r.party)
		if "Democrat" in parties and "Republican" in parties:
			bipartisan_cosp += 1
		
		if bill.bill_type == BillType.senate_bill:
			related_bill = None
			try:
				relation = bill.relatedbills.filter(relation='identical', related_bill__bill_type=BillType.house_bill).select_related("related_bill", "related_bill__sponsor").get()
				related_bill = relation.related_bill
			except Exception as e:
				continue
			if related_bill and related_bill.sponsor:
				total_has_companion += 1
				r = related_bill.sponsor.get_role_at_date(related_bill.introduced_date)
				if r:
					if bill.sponsor.role.party in ("Democrat", "Republican"):
						if r.party in ("Democrat", "Republican"):
							if bill.sponsor.role.party != r.party:
								total_companion_bipartisan += 1
		
	print congress, bipartisan_cosp, has_initial_cosponsors, total_companion_bipartisan, total_has_companion, total
	

from bill.models import *

delay_times = []

for bill in Bill.objects.filter(congress=111, bill_type=BillType.senate_bill):
	if bill.current_status in (BillStatus.introduced, BillStatus.reported):
		continue
	for d, st, descr in bill.major_actions:
		if st != BillStatus.introduced:
			#print BillStatus.by_value(st).label
			delay_times.append( eval(d).date() - bill.introduced_date )
			break
	
print "\n".join([str(d.total_seconds()/60/60/24) for d in delay_times])

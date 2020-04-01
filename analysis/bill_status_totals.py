#!script

from collections import defaultdict
import csv
import sys

from django.db.models import Count

from bill.models import *

# Collection congress/type/status pairs.
data = Bill.objects.filter(congress__gte=93).values("congress", "bill_type", "current_status").annotate(count=Count('id'))
data = list(data) # fetch all

# Replace numeric bill type and status with enum value and get the domain of statuses.
all_statuses = set()
all_bill_types = set()
for rec in data:
  rec["bill_type"] = BillType.by_value(rec["bill_type"])
  rec["current_status"] = BillStatus.by_value(rec["current_status"])
  all_statuses.add(rec["current_status"])
  all_bill_types.add(rec["bill_type"])

# Sort statuses in our canonical order.
all_statuses = sorted(all_statuses, key = lambda status : status.sort_order)

# Form a matrix.
matrix = defaultdict(lambda : 0)
for rec in data:
  matrix[(rec["congress"], rec["bill_type"], rec["current_status"])] += 1

# Output.
W = csv.writer(sys.stdout)
W.writerow(["congress", "bill type"] + [status.key for status in all_statuses])
for congress in range(min(rec["congress"] for rec in data), max(rec["congress"] for rec in data)+1):
  for bill_type in all_bill_types:
    W.writerow([congress, bill_type.label] + [matrix[(congress, bill_type, status)] for status in all_statuses])

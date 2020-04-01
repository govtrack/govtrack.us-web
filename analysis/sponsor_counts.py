#!script

from django.db.models import Count
from bill.models import Bill
import csv, sys

counts = { }
for b in Bill.objects.filter(
    #introduced_date__gte="2019-01-01"
    introduced_date__gte="2017-01-01", introduced_date__lte="2017-08-06"
  ).only("sponsor"):
  counts[b.sponsor] = counts.get(b.sponsor, 0) + 1

counts = sorted([[v, k] for (k, v) in counts.items()], key = lambda kv : -kv[0])

W = csv.writer(sys.stdout)
for count, person in counts:
  W.writerow([person, count])

#!script

import sys, csv

from person.models import *
from vote.models import *

stats = { }

for vv in Voter.objects.filter(
	vote__created__gte=sys.argv[1],
	vote__created__lte=sys.argv[2],
	vote__chamber=CongressChamber.by_key(sys.argv[3]),
	).values('person', 'option__key'):

	d = stats.setdefault(vv['person'], { "total": 0, "missed": 0 })
	d['total'] += 1
	if vv['option__key'] == "0":
		d['missed'] += 1

w = csv.writer(sys.stdout)
w.writerow(["person_id", "name", "eligible", "missed"])
people = Person.objects.in_bulk(stats.keys())
stats = sorted(stats.items(), key = lambda kv : kv[1]['missed']/float(kv[1]['total']))
for person, stats in stats:
	w.writerow([ person, people[person].name.encode("utf8"), stats['total'], stats['missed'] ])	

#!script

import sys, csv

from person.models import *
from vote.models import *

stats = { }

votes = Voter.objects.filter(
  vote__chamber=CongressChamber.by_key(sys.argv[1])
)
votes = votes.filter(person__in=set(Person.objects.filter(roles__current=True)))
if len(sys.argv) > 2:
	votes = votes.filter(vote__created__gte=sys.argv[2])
if len(sys.argv) > 3:
	votes = votes.filter(vote__created__lte=sys.argv[3])

for vv in votes.values('person', 'person_role', 'option__key'):
	d = stats.setdefault(vv['person'], { "total": 0, "count": 0, "role": None })
	d['total'] += 1
	if vv['option__key'] == "0":
		d['count'] += 1
	d['role'] = vv['person_role']

w = csv.writer(sys.stdout)
w.writerow(["person_id", "name", "eligible", "count"])
people = Person.objects.in_bulk(stats.keys())
roles = PersonRole.objects.in_bulk({ stat['role'] for stat in stats.values() })
stats = sorted(stats.items(), key = lambda kv : kv[1]['count']/float(kv[1]['total']))
for person, stats in stats:
	people[person].role = roles[stats['role']]
	w.writerow([ person, people[person].name, stats['total'], stats['count'] ])

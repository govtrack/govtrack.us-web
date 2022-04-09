#!script

import sys, csv

from django.db.models import Q
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

# When searching on "Present" votes, only include votes were aye/no were possible
# (i.e. exclude call by states and quorum calls etc).
#substantive_votes = Vote.objects.filter(Q(options__key="+") | Q(options__key="-"))
#votes = votes.filter(vote__in=substantive_votes)

for vv in votes.values('person', 'person_role', 'option__key'):
	d = stats.setdefault(vv['person'], { "total": 0, "count": 0, "role": None })
	d['total'] += 1
	if vv['option__key'] == "0":
#	if vv['option__key'] == "P":
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

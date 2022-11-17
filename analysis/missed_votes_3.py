#!script

import sys, csv

from django.db.models import Q
from person.models import *
from vote.models import *

stats = { }

votes = Voter.objects.filter(
  vote__congress=117,
  vote__chamber=CongressChamber.by_key(sys.argv[1]),
  voter_type=VoterType.member # VP can't be absent
)
#votes = votes.filter(person__in=set(Person.objects.filter(roles__current=True)))
if len(sys.argv) > 2:
	votes = votes.filter(vote__created__gte=sys.argv[2])
if len(sys.argv) > 3:
	votes = votes.filter(vote__created__lte=sys.argv[3])

# When searching on "Present" votes, only include votes were aye/no were possible
# (i.e. exclude call by states and quorum calls etc).
#substantive_votes = Vote.objects.filter(Q(options__key="+") | Q(options__key="-"))
#votes = votes.filter(vote__in=substantive_votes)

for vv in votes.values('person', 'person_role', 'option__key'):
	d = stats.setdefault(vv['person'], { "total": 0, 'missed': 0, "roles": set() })
	d['total'] += 1
	if vv['option__key'] == "0":
#	if vv['option__key'] == "P":
		d['missed'] += 1
	d['roles'].add(vv['person_role'])

w = csv.writer(sys.stdout)
w.writerow(["person_id", "name", "eligible", "missed"])
people = Person.objects.in_bulk(stats.keys())
roles = PersonRole.objects.in_bulk( sum([list(stat['roles']) for stat in stats.values()], []) )
stats = sorted(stats.items(), key = lambda kv : kv[1]['missed']/float(kv[1]['total']))
for person, stats in stats:
	people[person]._roles = { roles[r] for r in stats['roles'] }
	w.writerow([ person, get_person_name(people[person]),
	    stats['total'], stats['missed'] ])

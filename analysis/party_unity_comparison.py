#!script

import sys, csv, tqdm

from person.models import *
from vote.models import *

date_ranges = [(sys.argv[1], sys.argv[2]), (sys.argv[3], sys.argv[4])]

tuesday_group = { 412672, 412649, 412290, 400244, 400344, 412563, 412421, 412536, 412648, 400648, 412394, 412609, 412611, 412403, 412515, 412614, 400348, 412618, 400343, 400196, 412405, 412271, 412698, 400108, 412621, 400626, 412627, 412628, 412202, 412536, 412422, 412284, 412430, 412541, 412633, 412213, 412635, 412636, 412711, 412303, 412550, 412551, 412712, 412713, 412643, 412290, 400142, 412646, 412719, 412720, 400071, 412463, 412651, 412466, 412722, 400089, 412654, 400367, 412727, 412658, 412486, 400660, 412662 }

stats = { }
party_position_cache = { }

# Scan votes and compute totals for each Member how many times they voted
# with the majority of Republicans in each time range.
for i, date_range in enumerate(date_ranges):
	for vv in tqdm.tqdm(Voter.objects.filter(
		vote__created__gte=date_range[0],
		vote__created__lte=date_range[1],

		person__id__in=tuesday_group,
		#person_role__party="Republican",
		#vote__chamber=CongressChamber.house,

		option__key__in=("+", "-"),
		).values('vote__id', 'person', 'option__key', 'person_role__party')
		, desc=str(date_ranges[i])):

		pos_key = (vv['vote__id'], vv['person_role__party'])
		if pos_key in party_position_cache:
			party_position = party_position_cache[pos_key]
		else:
			v = Vote.objects.prefetch_related('voters', 'options').get(id=vv['vote__id'])
			totals = v.totals()
			party_totals = totals['party_counts'][totals['parties'].index(vv['person_role__party'])]
			if party_totals['yes'] > .66*party_totals['total']:
				party_position = '+'
			elif party_totals['no'] > .66*party_totals['total']:
				party_position = '-'
			else:
				party_position = 'n/a'
			party_position_cache[pos_key] = party_position

 		if party_position == 'n/a': continue

		d = stats.setdefault(vv['person'], [{ True: 0, False: 0 }, { True: 0, False: 0 }])
		d[i][vv['option__key'] == party_position] += 1

# Write out.
w = csv.writer(sys.stdout)
w.writerow(["person_id", "name", "Total1", "WithParty1", "Total2", "WithParty2"])
people = Person.objects.in_bulk(stats.keys())
for person, stats in stats.items():
	if stats[0][False] + stats[0][True] == 0 or stats[1][False] + stats[1][True] == 0: continue
	w.writerow([
		person,
		people[person].name.encode("utf8"),
		stats[0][False] + stats[0][True],
		float(stats[0][True]) / (stats[0][False] + stats[0][True]),
		stats[1][False] + stats[1][True],
		float(stats[1][True]) / (stats[1][False] + stats[1][True]),
		 ])	

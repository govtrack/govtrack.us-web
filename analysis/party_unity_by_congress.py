#!script

import sys, csv, tqdm, datetime

from us import get_congress_dates
from person.models import *
from vote.models import *

for congress in range(100, 115+1):
	stats = { True: 0, False: 0 }

	congress_dates = get_congress_dates(congress)

	all_votes = Voter.objects.filter(
		vote__congress=congress,
		created__lt=congress_dates[0] + datetime.timedelta(days=180),
		vote__chamber=CongressChamber.house,
		option__key__in=("+", "-"))\
		.values('vote__id', 'option__key', 'person_role__party')

	# compute vote totals by vote & party
	vote_totals = { }
	for vv in all_votes:
		key = (vv['vote__id'], vv['person_role__party'], vv['option__key'])
		vote_totals[key] = vote_totals.get(key, 0) + 1

		key = (vv['vote__id'], vv['person_role__party'])
		vote_totals[key] = vote_totals.get(key, 0) + 1
	
	# compute whether each vote(r) aligned with their party
	for vv in all_votes:
		if vote_totals[(vv['vote__id'], vv['person_role__party'], vv['option__key'])] > .66*vote_totals[(vv['vote__id'], vv['person_role__party'])]:
			stats[True] += 1
		elif vote_totals[(vv['vote__id'], vv['person_role__party'], "-" if vv['option__key'] == "+" else "+")] > .66*vote_totals[(vv['vote__id'], vv['person_role__party'])]:
			stats[False] += 1

	print congress, stats[True] / float(stats[False] + stats[True])

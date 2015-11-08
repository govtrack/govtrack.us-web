#!script

import sys, csv
from datetime import date, timedelta
from scipy.stats import percentileofscore
from numpy import median

from person.models import *
from vote.models import *

elections = {
	2008: date(2008, 11, 4),
	2012: date(2012, 11, 6),
	2016: date(2016, 11, 8),
}

super_tuesday = {
	2008: date(2008, 2, 5),
}

# All of the candidates for president that served at any point in Congress,
# plus the end date of their campaign --- the election date (for party nominees),
# or the date they conceded/withdrew.
candidates = {
	# 2016 Democratic candidates
	300022: { 2016: { "party": "D", "end": None },  # Clinton
	          2008: { "party": "D", "end": date(2008, 6, 7) } },
	400357: { 2016: { "party": "D", "end": None } }, # Sanders
	412249: { 2016: { "party": "D", "end": date(2015, 10, 20) } }, # Webb
	300020: { 2016: { "party": "D", "end": date(2015, 10, 23) } }, # Chafee

	# 2016 Republican candidates
	412573: { 2016: { "party": "R", "end": None } }, # Cruz
	300047: { 2016: { "party": "R", "end": None } }, # Graham
	400634: { 2016: { "party": "R", "end": None } }, # Jindal
	400590: { 2016: { "party": "R", "end": None } }, # Kasich
	412492: { 2016: { "party": "R", "end": None } }, # Rand Paul
	412491: { 2016: { "party": "R", "end": None } }, # Rubio
	300085: { 2016: { "party": "R", "end": None }  , # Santorum
	          2012: { "party": "R", "end": date(2012, 4, 10) } },

	# 2012 Republican candidates (except Santorum, above)
	400311: { 2012: { "party": "R", "end": date(2012, 5, 14) }  , # Ron Paul
	          2008: { "party": "R", "end": date(2008, 6, 12) } },
	404587: { 2012: { "party": "R", "end": date(2012, 5, 2) } }, # Gingrich
	412216: { 2012: { "party": "R", "end": date(2012, 1, 4) } }, # Bachman

	# 2008 Democratic candidates (except Clinton, above)
	400629: { 2008: { "party": "D", "end": elections[2008] } }, # Obama
	300039: { 2008: { "party": "D", "end": date(2008, 1, 30) } }, # Edwards
	300008: { 2008: { "party": "D", "end": date(2008, 1, 3) } }, # Biden
	300034: { 2008: { "party": "D", "end": date(2008, 1, 3) } }, # Dodd
	404738: { 2008: { "party": "D", "end": date(2008, 3, 13) } }, # Gravel
	400227: { 2008: { "party": "D", "end": date(2008, 1, 23) } }, # Kucinich

	# 2008 Republican candidates (except Ron Paul, above)
	300071: { 2008: { "party": "R", "end": elections[2008] } }, # McCain
	300158: { 2008: { "party": "R", "end": date(2008, 1, 22) } }, # Fred Thompson
	300158: { 2008: { "party": "R", "end": date(2008, 1, 30) } }, # Hunter
}

now = datetime.datetime.now()

# Begin output.
w = csv.writer(sys.stdout)
w.writerow(['start_date', 'end_date', 'chamber', "person_id", "name", "eligible", "missed", "missed_pct", "chamber_pctile"])

# Look at multiple election years.
for election_year, election_date in elections.items():
	# What time period of votes to look at? Use a one-year window before today,
	# and the corresponding window relative to the election day for past elections.
	window_end_date = election_date - (max(elections.values()) - now.date())
	window_end_date = window_end_date - timedelta(days=365)
	window_start_date = window_end_date - timedelta(days=364)

	# Compute stats for this time period, for each chamber.
	for chamber in (CongressChamber.house, CongressChamber.senate):
		# get stats of all members of the chamber
		stats = { }
		for vv in Voter.objects.filter(
			vote__chamber=chamber,
			vote__created__gte=window_start_date,
			vote__created__lte=window_end_date,
			).values('person', 'option__key'):
		
			d = stats.setdefault(vv['person'], { "total": 0, "missed": 0 })
			d['total'] += 1
			if vv['option__key'] == "0":
				d['missed'] += 1
	
		# rpeort stats for all candidates in this election
		reported_people = set(stats.keys()) & set(c for c in candidates if election_year in candidates[c])
		people = Person.objects.in_bulk(reported_people)
		all_scores = [s['missed'] / float(s['total']) for s in stats.values()]

		w.writerow([
			window_start_date, window_end_date, chamber,
			"", "MEDIAN",
			0, 0, round(median(all_scores)*100*10)/10, 50 ])

		for person in sorted(reported_people, key = lambda p : people[p].sortname):
			stat = stats[person]
			mp = stat['missed'] / float(stat['total'])

			role = PersonRole.objects.filter(person=people[person], startdate__lte=window_end_date, enddate__gte=window_start_date).order_by('-enddate').first()
			people[person].role = role # so get_person_name uses the role at the time the person was serving

			w.writerow([
				window_start_date, window_end_date, chamber,
				person, get_person_name(people[person]).encode("utf8"),
				stat['total'], stat['missed'], round(mp*100*10)/10, round(percentileofscore(all_scores, mp)) ])	

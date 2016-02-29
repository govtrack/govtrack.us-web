#!script

import sys, csv
from datetime import date, timedelta
from scipy.stats import percentileofscore, norm
from numpy import median

from person.models import *
from vote.models import *

days_before_election = 640
report_every_ndays = 10

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
	          2008: { "party": "D", "end": date(2008, 6, 7), "status": "highlight" } },
	400357: { 2016: { "party": "D", "end": None } }, # Sanders
	412249: { 2016: { "party": "D", "end": date(2015, 10, 20) } }, # Webb
	300020: { 2016: { "party": "D", "end": date(2015, 10, 23) } }, # Chafee

	# 2016 Republican candidates
	412573: { 2016: { "party": "R", "end": None } }, # Cruz
	300047: { 2016: { "party": "R", "end": date(2015, 12, 21) } }, # Graham
	400634: { 2016: { "party": "R", "end": date(2015, 11, 17) } }, # Jindal
	400590: { 2016: { "party": "R", "end": None } }, # Kasich
	412492: { 2016: { "party": "R", "end": date(2016, 2, 3) } }, # Rand Paul
	412491: { 2016: { "party": "R", "end": None } }, # Rubio
	300085: { 2016: { "party": "R", "end": date(2016, 2, 3) }  , # Santorum
	          2012: { "party": "R", "end": date(2012, 4, 10) } },

	# 2012 Republican candidates (except Santorum, above)
	400311: { 
		# 2012: { "party": "R", "end": date(2012, 5, 14) }  , # Ron Paul
	          2008: { "party": "R", "end": date(2008, 6, 12) } },
	#404587: { 2012: { "party": "R", "end": date(2012, 5, 2) } }, # Gingrich
	#412216: { 2012: { "party": "R", "end": date(2012, 1, 4) } }, # Bachman

	# 2008 Democratic candidates (except Clinton, above)
	400629: { 2008: { "party": "D", "end": elections[2008], "status": "nominee" } }, # Obama
	300039: { 2008: { "party": "D", "end": date(2008, 1, 30) } }, # Edwards
	300008: { 2008: { "party": "D", "end": date(2008, 1, 3) } }, # Biden
	#300034: { 2008: { "party": "D", "end": date(2008, 1, 3) } }, # Dodd
	#404738: { 2008: { "party": "D", "end": date(2008, 3, 13) } }, # Gravel
	#400227: { 2008: { "party": "D", "end": date(2008, 1, 23) } }, # Kucinich

	# 2008 Republican candidates (except Ron Paul, above)
	300071: { 2008: { "party": "R", "end": elections[2008], "status": "nominee" } }, # McCain
	300158: { 2008: { "party": "R", "end": date(2008, 1, 22) } }, # Fred Thompson
	300158: { 2008: { "party": "R", "end": date(2008, 1, 30) } }, # Hunter
}

now = datetime.datetime.now()

people = Person.objects.in_bulk(candidates)

trend_line_data = { }
window_data = []

def strftime(d):
	return d.strftime("%b %d, %Y").replace(" 0", " ")

# Look at multiple election years.
for election_year, election_date in elections.items():
	election_candidates = set(c for c in candidates if election_year in candidates[c])

	# What time period of votes to look at? Use a one-year window before today,
	# a one-year window before that, and the corresponding windows relative to
	# the election day for past elections.
	window1_end = election_date - (max(elections.values()) - now.date())
	window1_start = window1_end - timedelta(days=364)
	window0_end = window1_start - timedelta(days=1)
	window0_start = window0_end - timedelta(days=365)
	windows = [ [window0_start, window0_end], [window1_start, window1_end] ]

	# Compute stats for this time period, for each chamber.
	for chamber in (CongressChamber.house, CongressChamber.senate):
		stats = { }

		votes = Voter.objects.filter(vote__chamber=chamber)
		# get stats for all of the candidates in this election
		votes = votes.filter(
			vote__created__gte=min(window0_start, election_date-timedelta(days=days_before_election)), # cull data at SQL level
			vote__created__lte=election_date,
			)

		for vv in votes.values('person', 'option__key', 'vote__created'):
			vv['person'] = int(vv['person']) # comes as a long, which displays funny
			d = stats.setdefault(vv['person'], {
				"windows": [ [0,0], [0,0] ],
				"by-day": { }
			})

			# by window
			if window0_start <= vv['vote__created'].date() <= window0_end:
				d["windows"][0][0] += 1
				if vv['option__key'] == "0": d["windows"][0][1] += 1
			elif window1_start <= vv['vote__created'].date() <= window1_end:
				d["windows"][1][0] += 1
				if vv['option__key'] == "0": d["windows"][1][1] += 1
	
			# by day, to compute a trend line, for candidates only
			if vv['person'] in election_candidates:
				d['by-day'].setdefault(vv['vote__created'].date(), [0, 0])
				d['by-day'][vv['vote__created'].date()][0] += 1
				if vv['option__key'] == "0": d['by-day'][vv['vote__created'].date()][1] += 1

		# report window stats for all candidates in this election
		reported_people = set(stats.keys()) & election_candidates
		if len(reported_people) == 0: continue
		for window in (0, 1):
			# add a third term to the stat arrays for the percentage
			for s in stats.values():
				if s['windows'][window][0] == 0:
					s['windows'][window].append(None) # no votes in this window
				else:
					s['windows'][window].append( round(100.0 * s['windows'][window][1] / s['windows'][window][0] * 10.0)/10.0  )

			w = { "startiso": windows[window][0].isoformat(), "start": strftime(windows[window][0]), "end": strftime(windows[window][1]), "chamber": chamber.key, "election_year": election_year, "rows": [] }
			window_data.append(w)

			all_scores = [s['windows'][window][2] for s in stats.values() if s['windows'][window][2] is not None]
			median_score = median(all_scores)

			for person in sorted(reported_people, key = lambda p : people[p].sortname):
				role = PersonRole.objects.filter(person=people[person], startdate__lte=windows[window][1], enddate__gte=windows[window][0]).order_by('-enddate').first()
				people[person].role = role # so get_person_name uses the role at the time the person was serving
				w["rows"].append(
					  [get_person_name(people[person])]
					+ stats[person]['windows'][window]
				    + [round(percentileofscore(all_scores, stats[person]['windows'][window][2]))] )

			w["rows"].append(
				  ["MEDIAN"]
				+ [None, None, median_score, 50])

		# compute a trendline for each candidate
		for c in stats:
			# Find the date range to report for this candate: The
			# earliest vote within the days_before_election days
			# before the election to the last vote before the end
			# of the candidate's campaign (or if a current candidate,
			# today).
			if len(stats[c]['by-day']) == 0: continue # person had votes in one of the windows but is not a candidate
			day0 = max(min(stats[c]['by-day']), election_date-timedelta(days=days_before_election))
			day1 = min(max(stats[c]['by-day']), candidates[c][election_year]['end'] or now.date())

			# Compute a smooth trend line for this candidate using a normal
			# distribution-shaped rolling window, with the standard deviation
			# in days given in the scale parameter.
			weight_function = norm(loc=0, scale=14).pdf
			def value_on_day(date):
				# Compute the missed vote percent for this date,
				# using a gaussian-weighted window.
				if not (day0 <= date <= day1):
					# This date is out of range: Don't report
					# a value here. Because of the window, there
					# is something computable, but it is meaningless.
					return None
				calc = [0, 0]
				for d, (total_votes, missed_votes) in stats[c]['by-day'].items():
					if not (day0 <= d <= day1):
						# This date is out of range: clip the window so we
						# don't look at votes out of the range.
						continue
					dd = (date-d).days
					weight = weight_function(dd)
					calc[0] += weight * total_votes
					calc[1] += weight * missed_votes
				if calc[0] == 0:
					return None # no votes in window
				return round(100.0 * calc[1] / calc[0] * 10) / 10.0

			# Report the trend line value on the days leading up to the election.
			role = PersonRole.objects.filter(person=people[person], startdate__lte=election_date, enddate__gte=election_date).order_by('-enddate').first()
			people[person].role = role # so get_person_name uses the role at the time the person was serving
			trend_line_data[(election_year, c)] = {
				"name": "%s (%d)" % (get_person_name(people[c], firstname_position="before"), election_year),
				"legislator_name": get_person_name(people[c], firstname_position="before"),
				"election_year": election_year,
				"party": candidates[c][election_year]["party"],
				"status": candidates[c][election_year].get("status") or ("current" if candidates[c][election_year]['end'] is None else None),
				"data": [value_on_day(election_date + timedelta(days=d)) for d in range(-days_before_election, 0, report_every_ndays)]
			}

import json
print(json.dumps({
	"window_data": window_data,
	"report_every_ndays": report_every_ndays,
	"series": trend_line_data.values(),
	"now": (elections[max(elections)] - now.date()).days,
	"updated": strftime(now),
	"super_tuesday_2008": (elections[2008] - super_tuesday[2008]).days,
 }, indent=True, sort_keys=True))

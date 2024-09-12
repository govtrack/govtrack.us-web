#!script

import sys, csv
from datetime import date, timedelta
from scipy.stats import percentileofscore, norm
from numpy import mean, median

from person.models import *
from vote.models import *

days_before_election = 720
report_every_ndays = 10

elections = {
	2008: date(2008, 11, 4),
	2012: date(2012, 11, 6),
	2016: date(2016, 11, 8),
	2020: date(2020, 11, 3),
	2024: date(2024, 11, 5),
}

super_tuesday = {
	2008: date(2008, 2, 5),
	2012: date(2012, 3, 6),
	2016: date(2016, 3, 1),
	2020: date(2020, 3, 3),
	2024: date(2024, 3, 5),
}

super_tuesday_avg = int(round(mean([(elections[y] - super_tuesday[y]).days for y in elections])))

# All of the candidates for president that served at any point in Congress,
# plus the end date of their campaign --- the election date (for party nominees),
# or the date they conceded/withdrew.
candidates = {
	2024: {
		456876: { "party": "R", "end": elections[2024] }, # Vance for VP
	},

	2020: {
		# Democratic candidates
		300008: { "party": "D", "end": elections[2020] }, # Biden
		412223: { "party": "D", "end": elections[2020] }, # Gillibrand
		400357: { "party": "D", "end": elections[2020] }, # Sanders
		412678: { "party": "D", "end": elections[2020] }, # Harris
		412542: { "party": "D", "end": elections[2020] }, # Warren
		412598: { "party": "D", "end": elections[2020] }, # Booker
		412242: { "party": "D", "end": elections[2020] }, # Klobuchar
		412514: { "party": "D", "end": date(2019, 7, 8) }, # Swalwell
		412532: { "party": "D", "end": elections[2020] }, # Gabbard
		400352: { "party": "D", "end": elections[2020] }, # Ryan
		412632: { "party": "D", "end": elections[2020] }, # Moulton
		412575: { "party": "D", "end": elections[2020] }, # O'Rourke
		412544: { "party": "D", "end": elections[2020] }, # Delaney
		404738: { "party": "D", "end": date(2019, 7, 31) }, # Gravel
		400193: { "party": "D", "end": elections[2020] }, # Inslee
		412330: { "party": "D", "end": elections[2020] }, # Bennet
	},

	2016: {
		# Democratic candidates
		300022: { "party": "D", "end": elections[2016] },  # Clinton
		400357: { "party": "D", "end": date(2016, 7, 13) }, # Sanders
		412249: { "party": "D", "end": date(2015, 10, 20) }, # Webb
		300020: { "party": "D", "end": date(2015, 10, 23) }, # Chafee

		# Republican candidates
		412573: { "party": "R", "end": date(2016, 5, 3) }, # Cruz
		300047: { "party": "R", "end": date(2015, 12, 21) }, # Graham
		400634: { "party": "R", "end": date(2015, 11, 17) }, # Jindal
		400590: { "party": "R", "end": date(2016, 5, 4) }, # Kasich
		412492: { "party": "R", "end": date(2016, 2, 3) }, # Rand Paul
		412491: { "party": "R", "end": date(2016, 3, 15) }, # Rubio
		300085: { "party": "R", "end": date(2016, 2, 3) }, # Santorum
	},

	2012: {
		# Republican candidates
		400311: { "party": "R", "end": date(2012, 5, 14) }, # Ron Paul
		404587: { "party": "R", "end": date(2012, 5, 2) }, # Gingrich
		412216: { "party": "R", "end": date(2012, 1, 4) }, # Bachman
		300085: { "party": "R", "end": date(2012, 4, 10) }, # Santorum
	},

	2008: {
		# Democratic candidates
		400629: { "party": "D", "end": elections[2008], "status": "winner" }, # Obama
	        300022: { "party": "D", "end": date(2008, 6, 7), "status": "highlight" }, # Clinton
		300039: { "party": "D", "end": date(2008, 1, 30) }, # Edwards
		300008: { "party": "D", "end": date(2008, 1, 3) }, # Biden
		300034: { "party": "D", "end": date(2008, 1, 3) }, # Dodd
		404738: { "party": "D", "end": date(2008, 3, 13) }, # Gravel
		400227: { "party": "D", "end": date(2008, 1, 23) }, # Kucinich

		# 2008 Republican candidates
		300071: { "party": "R", "end": elections[2008], "status": "nominee" }, # McCain
		400311: { "party": "R", "end": date(2008, 6, 12) }, # Ron Paul
		300158: { "party": "R", "end": date(2008, 1, 22) }, # Fred Thompson
		300158: { "party": "R", "end": date(2008, 1, 30) }, # Hunter
	}
}

now = datetime.datetime.now()

all_candidate_ids = sum((list(candidate_ids) for candidate_ids in candidates.values()), [])
people = Person.objects.in_bulk(all_candidate_ids)

trend_line_data = { }

# For numerican results, we compute missed votes in two windows --- one window leading up to
# today (and corresponding dates before prior elections) and one "control" window before that,
# showing voting behavior before running for president. Since campaigns are usually about 1.75
# years long, the window will be the duration from 1.75 years before the election to today.
current_days_to_election = max(elections.values()) - now.date()
window_size = round( ( now.date() - (max(elections.values()) - timedelta(days=365*1.75)) ).days / 30 ) * 30
window_data = []

def strftime(d):
	return d.strftime("%b %d, %Y").replace(" 0", " ")

# Look at multiple election years.
for election_year, election_date in elections.items():
	election_candidates = set(candidates[election_year].keys())

	# What time period of votes to look at for the numerical analysis?
	window1_end = election_date - current_days_to_election
	window1_start = window1_end - timedelta(days=window_size)
	window0_end = window1_start - timedelta(days=1)
	window0_start = window0_end - timedelta(days=window_size)
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
			if len(all_scores) == 0: # we haven't yet entered the window
				continue
			median_score = median(all_scores)

			for person in sorted(reported_people, key = lambda p : people[p].sortname_strxfrm):
				role = PersonRole.objects.filter(person=people[person], startdate__lte=windows[window][1], enddate__gte=windows[window][0]).order_by('-enddate').first()
				people[person].role = role # so get_person_name uses the role at the time the person was serving
				if not stats[person]['windows'][window][2]: continue
				w["rows"].append(
					  [people[person].get_absolute_url(), get_person_name(people[person])]
					+ stats[person]['windows'][window]
				    + [round(percentileofscore(all_scores, stats[person]['windows'][window][2]))] )

			w["rows"].append(
				  ["", "MEDIAN"]
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
			day1 = min(max(stats[c]['by-day']), candidates[election_year][c]['end'] or now.date())

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
			role = PersonRole.objects.filter(person=people[c], startdate__lte=election_date, enddate__gte=election_date).order_by('-enddate').first()
			people[c].role = role # so get_person_name uses the role at the time the person was serving
			trend_line_data[(election_year, c)] = {
				"name": "%s (%d)" % (get_person_name(people[c], firstname_position="before"), election_year),
				"legislator_name": get_person_name(people[c], firstname_position="before"),
				"sort_name": get_person_name(people[c], firstname_position="after"),
				"link": people[c].get_absolute_url(),
				"election_year": election_year,
				"party": candidates[election_year][c]["party"],
				"status": candidates[election_year][c].get("status") or ("current" if candidates[election_year][c]['end'] is None else None),
				"data": [value_on_day(election_date + timedelta(days=d)) for d in range(-days_before_election+report_every_ndays, 0, report_every_ndays)]
			}

# Sort the series by year and name.
trend_line_data = list(trend_line_data.values())
trend_line_data.sort(key = lambda s : (-s["election_year"], s["status"] is None, s["sort_name"]))

import json
print(json.dumps({
	"window_size": window_size,
	"window_data": window_data,
	"report_every_ndays": report_every_ndays,
	"series": trend_line_data,
	"now": (elections[max(elections)] - now.date()).days,
	"updated": strftime(now),
	"elections": list(elections),
	"super_tuesday": super_tuesday_avg,
 }, indent=True, sort_keys=True))

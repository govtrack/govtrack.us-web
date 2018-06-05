#!script

# Compute missed votes % for Members of Congress and summary
# statistics by chamber.

# To update from scratch:
# for c in {1..113}; do echo $c; python missed_votes.py $c; done

import csv, datetime, glob, os, re, sys
import lxml.etree as lxml
from scipy.stats import percentileofscore, scoreatpercentile

congress = int(sys.argv[1])
datadir = "data/us/%d/" % congress

# UTILS

def parse_datetime(value):
	try:
		return datetime.datetime.strptime(value, '%Y-%m-%d').date()
	except ValueError:
		try:
			return datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%S-05:00').date()
		except ValueError:
			return datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%S-04:00').date()

# BEGIN

# prepare output data directories
os.system("mkdir -p " + datadir + "stats/person/missedvotes")

# load in the session dates so we know how to break them down into smaller time periods
session_dates = { }
for rec in csv.DictReader(open("../data/us/sessions.tsv"), delimiter="\t"):
	session_dates[(int(rec['congress']), rec['session'])] = (parse_datetime(rec['start']), parse_datetime(rec['end']))

def date_to_month_index(date):
	return date.year*12 + (date.month-1)
	
def get_date_bin(congress, session, date):
	# Bin the dates roughly in three-month periods, but align the bins to sessions of Congress *and* to months.
	d1, d2 = session_dates[(congress, session)]
	if date < d1 or date > d2: raise ValueError("Date out of range!")
	d = date_to_month_index(d2) - date_to_month_index(d1)
	n_periods = d / 3
	if n_periods < 2: return 0
	dp = d / n_periods
	return int((date_to_month_index(date) - date_to_month_index(d1)) / dp)

# GLOB

session_bin_dates = { }
vote_counts = { }
voters_by_chamber = { "h": set(), "s": set() }
person_lifetime_vote_dates = { }
for fn in glob.glob(datadir + "rolls/*.xml"):
	m = re.search(r"/([hs])([^/]+)-\d+.xml$", fn)
	where, session = m.groups()
	
	dom = lxml.parse(fn).getroot()
	date = parse_datetime(dom.get("datetime"))
	bin = (congress, session, where, get_date_bin(congress, session, date))
	
	if not bin in session_bin_dates:
		session_bin_dates[bin] = (date, date)
	else:
		session_bin_dates[bin] = (min(session_bin_dates[bin][0], date), max(session_bin_dates[bin][1], date))
		
	for voter in dom.xpath("voter[@id]"):
		id = int(voter.get("id"))
		if id == "0": raise ValueError()
		ctr = vote_counts.setdefault(id, {}).setdefault(bin, { "total": 0, "missed": 0 })
		ctr['total'] += 1
		if voter.get("vote") == "0": ctr['missed'] += 1
		
		voters_by_chamber[where].add(id)
		
		if not (where, id) in person_lifetime_vote_dates:
			person_lifetime_vote_dates[(where, id)] = (date, date)
		else:
			person_lifetime_vote_dates[(where, id)] = (min(person_lifetime_vote_dates[(where, id)][0], date), max(person_lifetime_vote_dates[(where, id)][1], date))
		
# Stop-gap measure for start of Congress when no votes have occurred in one chamber or the other.
# Get a complete list of Members via the GovTrack API. We need to know who so we bring forward
# any historical data.
if len(voters_by_chamber['h']) == 0 or len(voters_by_chamber['s']) == 0:
	import json, urllib.request, urllib.parse, urllib.error
	voters_by_chamber = { "h": set(), "s": set() }
	for m in json.load(urllib.request.urlopen("http://www.govtrack.us/api/v1/person/?roles__current=true&limit=600"))["objects"]:
		c = "s" if (m["current_role"]["role_type"] == "senator") else "h"
		voters_by_chamber[c].add( int(m["id"]) ) 
	
if len(voters_by_chamber['h']) == 0 or len(voters_by_chamber['s']) == 0:
	print("missed_votes: There are no voters in one of the chambers. Which means we don't know who is currently serving....")
	sys.exit(0)

# For each Member of Congress, search for the most recent Congress that has their
# statistics, since they might have been in an earlier Congress than the previous,
# and load in the statistics from their stats file, which includes all historical data to
# that point. Also update the person's lifetime vote dates.
for p in voters_by_chamber['h'] | voters_by_chamber['s']:
	for cc in range(congress-1, 0, -1):
		fn = "../data/us/%d/stats/person/missedvotes/%d.csv" % (cc, p)
		if os.path.exists(fn):
			for rec in csv.DictReader(open(fn)):
				# currently serving but has not voted in this chamber in this Congress yet
				if p not in vote_counts: vote_counts[p] = { }
				
				if rec["congress"] == "lifetime":
					# carry forward the whole record. if the member is not currently serving in the chamber,
					# we will not recompute the lifetime total, but we will output it in their individual stats file.
					bin = ('lifetime', rec["chamber"])
					vote_counts[p][bin] = {
						"total": int(rec["total_votes"]),
						"missed": int(rec["missed_votes"]),
						"percent": float(rec["percent"]),
						"percentile": float(rec["percentile"]),
						"pctile25": float(rec["pctile25"]),
						"pctile50": float(rec["pctile50"]),
						"pctile75": float(rec["pctile75"]),
						"pctile90": float(rec["pctile90"]),
						}

					# update the lifetime votes date range
					if (rec["chamber"], p) not in person_lifetime_vote_dates:
						# person served in a different chamber than what he serves in the current congress
						person_lifetime_vote_dates[(rec["chamber"], p)] = (parse_datetime(rec["period_start"]), parse_datetime(rec["period_end"]))
					else:
						person_lifetime_vote_dates[(rec["chamber"], p)] = (min(person_lifetime_vote_dates[(rec["chamber"], p)][0], parse_datetime(rec["period_start"])), max(person_lifetime_vote_dates[(rec["chamber"], p)][1], parse_datetime(rec["period_end"])))
				else:
					bin = (int(rec["congress"]), rec["session"], rec["chamber"], rec["period"])
					session_bin_dates[bin] = (parse_datetime(rec["period_start"]), parse_datetime(rec["period_end"]))
					vote_counts[p][bin] = { "total": int(rec["total_votes"]), "missed": int(rec["missed_votes"]) }
			break # don't look at previous congresses, we have their house and senate records both here

# Compute lifetime missed vote totals by chamber for currently serving members in that chamber.
for where in ('h', 's'):
	for p in voters_by_chamber[where]:
		# currently serving but has not voted in this chamber in this Congress yet
		if p not in vote_counts: vote_counts[p] = { }
			
		vote_counts[p][('lifetime', where)] = {
			"total": sum(bv["total"] for bk, bv in vote_counts[p].items() if bk[0] != "lifetime" and bk[2] == where),
			"missed": sum(bv["missed"] for bk, bv in vote_counts[p].items() if bk[0] != "lifetime" and bk[2] == where),
		}
		if vote_counts[p][('lifetime', where)]['total'] == 0:
			del vote_counts[p][('lifetime', where)]
		
# Compute medians and percentiles.
for bin in [("lifetime", "s"), ("lifetime", "h")] + sorted(session_bin_dates):
	if bin[0] != "lifetime":
		# Get Members of Congress that were present in the bin.
		plist = [p for p in vote_counts if bin in vote_counts[p]]
	else:
		# Get Members of Congress that were present in the chamber this congress.
		# Other Members in Congress this congress may have previously served in this chamber and
		# will have a lifetime record, but we don't want them influencing the current percentiles and
		# we don't want them to appear in output.
		#
		# Filter out individuals who haven't voted yet. They get included if
		# there is no vote in a chamber and we pull the ID list from GovTrack.
		plist = list(voters_by_chamber[bin[1]])
	
	# Compute their % missed votes and store in a flat list.
	values = []
	for p in plist:
		if bin not in vote_counts[p]: continue # when doing lifetime stats, is a member currently serving but has not voted
		binctr = vote_counts[p][bin]
		binctr['percent'] = float(binctr['missed']) / float(binctr['total']) * 100.0
		values.append(binctr['percent'])
		
	# Has there been any votes in the chamber in this period? Only
	# really happens at the start of a Congress. One chamber may
	# not have voted yet.
	if len(values) == 0:
		print("No data for", bin)
		continue
		
	# For each of them, store the percentile and the (bin-wide) median.
	bin_percentiles = { "pctile25": scoreatpercentile(values, 25), "pctile50": scoreatpercentile(values, 50), "pctile75": scoreatpercentile(values, 75), "pctile90": scoreatpercentile(values, 90) }
	for p in plist:
		if bin not in vote_counts[p]: continue # when doing lifetime stats, is a member currently serving but has not voted
		binctr = vote_counts[p][bin]
		binctr['percentile'] = percentileofscore(values, binctr['percent'], kind='strict')
		binctr.update(bin_percentiles)
		
	if bin[0] == "lifetime":
		# Write out the lifetime statistics in a main file sorted by percentile.
		# (The user can compute his own median here.)
		
		# filter out MoCs that are currently serving but have not voted yet
		plist = [p for p in plist if bin in vote_counts[p]]
		
		plist.sort(key = lambda p : -vote_counts[p][bin]['percentile'])
		w = csv.writer(open(datadir + "stats/missedvotes_%s.csv" % bin[1], "w"))
		w.writerow(["id", "total_votes", "missed_votes", "percent", "percentile", "first_vote_date", "last_vote_date"])
		for p in plist:
			# when doing lifetime stats, is a member currently serving but has not voted, so omit from stats
			# since it might indicate we included that person in medians, but we didn't.
			v = vote_counts[p][bin]
			w.writerow([p, v['total'], v['missed'], v['percent'], v['percentile'], person_lifetime_vote_dates[(bin[1], p)][0].isoformat(), person_lifetime_vote_dates[(bin[1], p)][1].isoformat()])
		
# Write out statistics by Member of Congress. Although we're only writing out currently serving MoCs,
# include their lifetime records for both the house and senate.
for p in vote_counts:
	w = csv.writer(open(datadir + "stats/person/missedvotes/%d.csv" % p, "w"))
	# columns are tied to how we load in historical data above
	w.writerow(["congress", "session", "chamber", "period", "total_votes", "missed_votes", "percent", "percentile", "period_start", "period_end", "pctile25", "pctile50", "pctile75", "pctile90"])
	for bin in sorted(vote_counts[p]):
		v = vote_counts[p][bin]
		if bin[0] == "lifetime":
			dates = person_lifetime_vote_dates[(bin[1], p)]
		else:
			dates = session_bin_dates[bin]
		if len(bin) == 2: bin = [bin[0], None, bin[1], None]
		w.writerow(list(bin) + [v['total'], v['missed'], v['percent'], v['percentile'], dates[0].isoformat(), dates[1].isoformat(), v['pctile25'], v['pctile50'], v['pctile75'], v['pctile90']])
		

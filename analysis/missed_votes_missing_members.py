#!script

# Find legislators who are missing by looking at their recent missed votes.

# missed_votes_missing_members.py CONGRESS

import csv, datetime, glob, os.path, re, sys, math
import lxml.etree as lxml
from scipy.stats import percentileofscore, scoreatpercentile

congress = int(sys.argv[1])
output_file = "data/analysis/by-congress/%d/missinglegislators.csv" % congress

# UTILS

def parse_datetime(value):
	try:
		return datetime.datetime.strptime(value, '%Y-%m-%d')
	except ValueError:
		try:
			return datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%S-05:00')
		except ValueError:
			return datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%S-04:00')

# BEGIN

# prepare output data directories
os.system("mkdir -p " + os.path.dirname(output_file))

# Load in all missed votes data by legislator tracking (date, present/absent) pairs.
# scan the previous congress so we have continuity at the start of the next congress
recent_votes = { }
for c in (congress-1, congress):
	vote_xml_glob = "data/congress/%d/votes/*/*/data.xml" % c
	for fn in glob.glob(vote_xml_glob):
		# This vote ocurred in closed session and at the time of initial publication, all senators were
		# marked as not voting, which dinged every senator as having a missed vote. We'll skip this
		# vote in statistics. The Senate XML file is expected to be updated to mark the senators'
		# votes as something other than Not Voting, and when that happens this will become unnecessary.
		if "congress/116/votes/2020/s216/" in fn: continue

		m = re.match("data/congress/\d+/votes/(.*)/.*/", fn)
		dom = lxml.parse(fn).getroot()
		chamber = dom.get("where")[0] # h, s
		date = parse_datetime(dom.get("datetime"))

		for voter in dom.xpath("voter[@id]"):
			id = int(voter.get("id"))
			if id == "0": raise ValueError()

			r = recent_votes.setdefault(id, [])
			r.append((date, chamber, voter.get("vote") == "0"))

# Since we didn't glob in order, sort.
# Do a reverse sort since we're interested in absences leading to now.
for votes in recent_votes.values():
	votes.sort(reverse=True)

# Find the most recent vote by chamber so we can exclude legislators no longer serving.
last_vote_date = { }
for votes in recent_votes.values():
	date, chamber, vote = votes[0]
	if chamber not in last_vote_date or date > last_vote_date[chamber]:
		last_vote_date[chamber] = date

# Find the length of the worst stretch leading to now for each legislator.
runs = []
for id, votes in recent_votes.items():
	# Skip legislators no longer serving.
	if votes[0][0] != last_vote_date[votes[0][1]]:
		continue

	# Find the date with the highest missed votes percent between it and now,
	# but weigh recent days less because if the legislator is currently in
	# a short total absense it will be 100% and we wouldn't see prolonged
	# partial absences.
	missed = 0
	run = None
	for i, (date, chamber, vote) in enumerate(votes):
		if vote:
			missed += 1
			missedpct = missed / (i + 1)
			w = math.log((votes[0][0] - date).days + 10)
			if run is None or missedpct * w >= run["weighted_missed_pct"]:
				run = { "missed": missed, "total": i + 1, "missedpct": missedpct,
					"weighted_missed_pct": missedpct * w,
					"first": date, "last": votes[0][0],
					"id": id, "chamber": votes[0][1] }
	if not run: continue

	# Don't ding members missing less than one half of votes.
	if run["missedpct"] < 1/2: continue

	# Don't ding members missing for less than 5 days because we can't research
	# absences fast enough to contextualize these, which are probably minor.
	if (run["last"].date() - run["first"].date()).days < 5: continue

	# In recesses, legislators don't have an opportunity to return from a short
	# absense. Skip runs that are shorter than the length of the recess so far.
	# If votes continued at the same pace during the recess, that would put
	# the missed votes percent lower than the cutoff below.
	if run["last"] - run["first"] < datetime.datetime.now() - votes[0][0]: continue

	runs.append(run)

# Sort members by duration of the run.
runs.sort(key = lambda r : r["first"])

# Write out.
W = csv.writer(open(output_file, "w"))
W.writerow(["person", "missedvotes", "totalvotes", "firstmissedvote", "lastvote", "lastchamber"])
for run in runs:
	W.writerow([run["id"], run["missed"], run["total"], run["first"].isoformat(), run["last"].isoformat(), run["chamber"]])


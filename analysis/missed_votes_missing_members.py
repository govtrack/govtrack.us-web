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
	# partial absences. Scan the vots from most recent to least recent.
	missed = 0
	run = None
	last_voted = None
	for i, (date, chamber, novote) in enumerate(votes):
		if novote:
			missed += 1
			missedpct = missed / (i + 1)
			w = math.log((votes[0][0] - date).days + 10)
			if run is None or missedpct * w >= run["weighted_missed_pct"]:
				run = { "missed": missed, "total": i + 1, "missedpct": missedpct,
					"weighted_missed_pct": missedpct * w,
					"first": date, "last": votes[0][0],
					"legislative_days": len(set(v[0].date() for v in votes[:i+1])),
					"id": id, "chamber": votes[0][1] }
		elif last_voted is None:
			last_voted = i
	if not run: continue

	if last_voted is not None: run["last_voted"] = votes[last_voted][0]

	# Don't ding members missing less than one half of votes.
	if run["missedpct"] < 1/2: continue

	# Don't ding members missing for less than 10 days because we can't research
	# absences fast enough to contextualize thesee, which are probably minor, and
	# with more entries the list becomes noisy and people complain that we are
	# unfairly dinging legislators.
	if (run["last"].date() - run["first"].date()).days < 10: continue

	# Don't ding members missing for less than 3 legislative days because single-day
	# absences are not uncommon.
	if run["legislative_days"] < 3: continue

	# In recesses, legislators don't have an opportunity to return from a short
	# absense. Skip runs that are shorter than the length of the recess so far.
	# If votes continued at the same pace during the recess, that would put
	# the missed votes percent lower than the cutoff below.
	if run["last"] - run["first"] < datetime.datetime.now() - votes[0][0]: continue

	# The legislator may have returned from an absence but overall still not
	# yet gone under the threshold to drop off this list. Find a bisecting
	# point in the run that maximizes the differenc between the missed votes
	# percent before and after. If the legislator is totally back then the
	# recent missed votes percent will be zero so a ratio would be hard, and
	# we should bias for longer return time spans.
	missed = 0
	for i in range(run["total"] - 1):
		if votes[i][2]: missed += 1
		mp1 = missed / (i + 1)
		mp2 = (run["missed"] - missed) / (run["total"] - (i + 1))
		d = mp2 - mp1
		if d >= run.get("return", {}).get("d", 0):
			run["return"] = {
				"d": d,
				"missed": missed, "total": i + 1,
				"first": votes[i][0], "last": votes[0][0],
				"runlast": votes[i+1][0],
			}
	if run.get("return", {}).get("d", 0) > .5:
		# Update the run to reflect the worst portion.
		run.update({
			"missed": run["missed"] - run["return"]["missed"],
			"total": run["total"] - run["return"]["total"],
			"missedpct": None, # clear, not used beyond this point
			"last": run["return"]["runlast"],
		})
	elif "return" in run:
		del run["return"]

	runs.append(run)

# Sort members first by whether they have returned and then by duration of the run.
runs.sort(key = lambda r : ("return" in r, r["first"]))

# Write out.
W = csv.writer(open(output_file, "w"))
W.writerow(["person", "lastchamber",
	"missedvotes", "totalvotes", "firstmissedvote", "lastvote", "lastpresent",
	"returnstart", "returnlastvote", "returnmissedvotes", "returntotalvotes"])
for run in runs:
	W.writerow(
		[run["id"], run["chamber"],
		run["missed"], run["total"], run["first"].isoformat(), run["last"].isoformat(),
		run["last_voted"].isoformat() if "last_voted" in run else None]
		+ ([ run["return"]["first"].isoformat(), run["return"]["last"].isoformat(), run["return"]["missed"], run["return"]["total"] ] if "return" in run else []))


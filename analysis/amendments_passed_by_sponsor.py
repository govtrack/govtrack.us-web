#!script

from collections import defaultdict
from glob import glob
import os.path
import json
import csv, sys

import yaml

from person.models import Person

# Get current Members of Congress.
people = yaml.load(open("data/congress-legislators/legislators-current.yaml"))
people_map = {
	person["id"]["thomas"]: Person.objects.get(id=person["id"]["govtrack"])
	for person in people
}

people_map['01631'] = Person.objects.get(id=300022) # Hillary Clinton
print people_map['01631']

# Count up by scanning files. Our in-database data is missing actions and
# isn't well-linked to votes, at least in historical data.
counts = defaultdict(lambda : defaultdict(lambda : 0))
meta = defaultdict(lambda : defaultdict(lambda : None))
for congress in range(93, 114+1):
	for fn in glob("data/congress/%d/amendments/*/*" % congress):
		with open(os.path.join(fn, 'data.json')) as f:
			amdt = json.load(f)

			if amdt["sponsor"]["type"] != "person": continue # amendments can be sponsored by committees

			# Get sponsor & status.
			sponsor = amdt["sponsor"]["thomas_id"]
			if sponsor not in people_map: continue
			status = amdt["status"]
			if status not in ("offered", "pass", "fail", "withdrawn"): raise Exception()

			# Bernie said "roll call" amendments, so only look at amendments that got
			# a roll call vote.
			had_roll_call = False
			for action in amdt["actions"]:
				if action["type"] == "vote":
					if action["how"] == "roll":
						had_roll_call = True
			if not had_roll_call: continue

			# Increment metadata.
			if not meta[sponsor]["first"]:
				meta[sponsor]["first"] = amdt["status_at"]
				meta[sponsor]["last"] = amdt["status_at"]
			else:
				meta[sponsor]["first"] = min(meta[sponsor]["first"], amdt["status_at"])
				meta[sponsor]["last"] = max(meta[sponsor]["last"], amdt["status_at"])

			# Increment counter.
			counts[sponsor]["total"] += 1
			if status == "pass":
				counts[sponsor]["passed"] += 1

# Report.
w = csv.writer(sys.stdout)
for sponsor, results in sorted(counts.items(), key=lambda kv : kv[1]["passed"]):
	w.writerow([
		people_map[sponsor].id,
		people_map[sponsor].name.encode("utf8"), #sortname?
		meta[sponsor]["first"],
		meta[sponsor]["last"],
		results["total"],
		results["passed"],
	])

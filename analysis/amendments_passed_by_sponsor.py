#!script

from collections import defaultdict
from glob import glob
import os.path
import json
import csv, sys
import tqdm

import yaml

from person.models import Person

CONGRESS_PROJECT_PATH = "../congress-project-wdir"

# Get a mapping from the old THOMAS IDs and Bioguide IDs to current Members of Congress.
people = yaml.load(open(CONGRESS_PROJECT_PATH + "/congress-legislators/legislators-current.yaml"))
people_map = { ("govtrack", key): value for (key, value) in Person.objects.in_bulk(person["id"]["govtrack"] for person in people).items() }
for person in people:
  for key, value in person["id"].items():
    if key in ("thomas", "bioguide"):
      people_map[(key, value)] = people_map[("govtrack", person["id"]["govtrack"])]

#people_map['01631'] = Person.objects.get(id=300022) # Hillary Clinton, used this during the 2016 election season
#print(people_map['01631'])

# Count up by scanning files. Our in-database data is missing actions and
# isn't well-linked to votes, at least in historical data. First form a file list.
amendment_file_list = glob(CONGRESS_PROJECT_PATH + "/data/*/amendments/*/*")

# Scan the files.
counts = defaultdict(lambda : defaultdict(lambda : 0))
meta = defaultdict(lambda : defaultdict(lambda : None))
for fn in tqdm.tqdm(amendment_file_list):
		with open(os.path.join(fn, 'data.json')) as f:
			amdt = json.load(f)

			if amdt["sponsor"]["type"] != "person": continue # amendments can be sponsored by committees

			# Get sponsor.
			for id_type in ("thomas", "bioguide"):
				if id_type + "_id" in amdt["sponsor"]:
					sponsor = people_map.get( (id_type, amdt["sponsor"][id_type + "_id"]) )
					if sponsor: break
			else:
				# Amendment's sponsor is not currently serving.
				continue

			# Get status.
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
w.writerow([
	"Sponsor ID",
	"Sponsor Name",
	"Earliest Amendment Vote Date",
	"Latest Amendment Vote Date",
	"Total",
	"Passed"
])
for sponsor, results in sorted(counts.items(), key=lambda kv : kv[1]["passed"], reverse=True):
	w.writerow([
		sponsor.id,
		sponsor.name,
		meta[sponsor]["first"],
		meta[sponsor]["last"],
		results["total"],
		results["passed"],
	])

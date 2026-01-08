#!script

import csv, sys
from person.models import Person

congress = int(sys.argv[1])

w = csv.writer(sys.stdout)

fields = ["chamber", "name", "state", "percent", "percentile", "missed_votes", "total_votes", "first_vote_date", "last_vote_date"]
w.writerow(fields)

for chamber in ('h', 's'):
	for rec in csv.DictReader(open(f"data/analysis/by-congress/{congress}/missedvotes_{chamber}.csv")):
		p = Person.objects.get(id=rec["id"])
		if not p.current_role: continue
		rec["chamber"] = "Senate" if chamber == "s" else "House"
		rec["name"] = p.name
		rec["state"] = p.current_role.state
		for f in ("percent", "percentile"): rec[f] = str(round(float(rec[f]), 1))
		w.writerow([rec[f] for f in fields])
		

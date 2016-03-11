#!script

import csv, sys
from person.models import Person

w = csv.writer(sys.stdout)

fields = ["chamber", "name", "state", "percent", "percentile", "missed_votes", "total_votes", "first_vote_date", "last_vote_date"]
w.writerow(fields)


for hs in ('h', 's'):
	for rec in csv.DictReader(open("data/us/114/stats/missedvotes_%s.csv" % hs)):
		p = Person.objects.get(id=rec["id"])
		if not p.current_role: continue
		rec["chamber"] = "Senate" if hs == "s" else "House"
		rec["name"] = p.name
		rec["state"] = p.current_role.state
		w.writerow([rec[f].encode("utf8") for f in fields])
		

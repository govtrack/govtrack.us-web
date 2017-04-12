#!script
import csv, sys, re, datetime

from vote.models import Vote, VoteCategory
from vote.views import get_vote_matrix

# Select votes.
votes = Vote.objects.filter(session=sys.argv[1], category=VoteCategory.nomination,
   created__gte=datetime.datetime(int(sys.argv[1]), 1, 20, 12, 0, 0))

# Compute matrix.
votes, party_totals, voters = get_vote_matrix(votes.order_by('created'))

# Write out.
w = csv.writer(sys.stdout)

# Wrote column headers.
w.writerow(["Name", "Party", "Total Yes", "Total No"]
	+ [re.sub("^On the Nomination ", "", v.question).encode("utf8") for v in votes])
w.writerow(["", "", "", ""]
	+ [v.created.strftime("%x") for v in votes])
w.writerow(["", "", "", ""]
	+ [v.result.encode("utf8") for v in votes])

w.writerow([])

# Write party totals.
for party_total in party_totals:
	if party_total["party"] == "Vice President":
		name = party_total["party"], ""
	else:
		name = "All", party_total["party"] + "s"
	w.writerow([ name[0], name[1], "", "" ]
		+ ["{yes} yes, {no} no".format(**pt)
		   if pt is not None else ""
	       for pt in party_total["votes"]])

w.writerow([])

# Write voters.
voters.sort(key = lambda voter : -voter["total_plus"])
for voter in voters:
	if voter.get("party") == "Vice President": continue # confusing, already shown in the party totals
	w.writerow([ voter["person_name"].encode("utf8"), voter.get("party", "[Changed]"), voter["total_plus"], voter["total_votes"]-voter["total_plus"] ]
	  + [v.option.norm_text if v is not None else "Not Serving"
	     for v in voter["votes"]
        ])

#!script

import sys, csv
from django.db.models import Count
from person.models import Person
from vote.models import Voter, VoteCategory

w = csv.writer(sys.stdout)

# Get the votes that Ron Paul participated in.
# Exclude votes for Speaker by looking only at
# the usual +/-/0/P options.
all_votes = Voter.objects.filter(
	person_id=400311,
	option__key__in=("+", "-", "0", "P"),
	vote__source=2, # house.gov, not historical
	)\
	.select_related("option")

# What are his totals?
w.writerow(["Ron Paul Totals"])
option_keys = { "0": "Not Voting", "P": "Present (Abstain/Quorum Call)", "-": "Nay/No", "+": "Aye/Yea", "total": "Total" }
by_vote = list(all_votes.values_list("option__key").annotate(count=Count('id')))
by_vote.sort(key = lambda v : -v[1])
for option, count in by_vote:
	w.writerow([option_keys[option], count])

# Convert this into a list of Vote objects, i.e.
# the Votes that Ron Paul was elligible for.
all_votes = all_votes.values_list("vote", flat=True)

# Get the members that also were elligible for those votes,
# and of those the ones *most* elligible, meaning served most
# in this time period...
other_reps = Voter.objects.filter(vote__in=set(all_votes))\
	.values_list("person__id").annotate(count=Count('id')).order_by("-count")[0:150]
other_reps = set([rep for rep, count in other_reps])

# Now get their counts.
all_votes = Voter.objects.filter(
	person_id__in=other_reps,
	vote__in=all_votes,
	option__key__in=("+", "-", "0", "P"))\
	.select_related("option")
by_vote = list(all_votes.values_list("person__id", "option__key").annotate(count=Count('id')))
by_voter = { }
for person, vote, count in by_vote:
	by_voter.setdefault(person, {})[vote] = count
	by_voter[person]["total"] = by_voter[person].get("total", 0) + count
by_voter = sorted(by_voter.items(), key = lambda kv : -kv[1]["total"])
w.writerow(["Other Reps Serving In The Same Time"])
cols = ("+", "-", "0", "P", "total")
w.writerow(["person", "name"] + [option_keys[c] for c in cols])
for person, votes in by_voter:
	w.writerow([ person, str(Person.objects.get(id=person)) ] + [votes[col] for col in cols])

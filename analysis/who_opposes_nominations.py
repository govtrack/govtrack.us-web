#!script

import sys, csv
from vote.models import Voter, VoteCategory

# Count up votes by person and option.
all_votes = Voter.objects.filter(
    vote__category=VoteCategory.nomination,
#    vote__congress__gte=113)
    vote__created__gte="2009-01-20")
all_votes = all_votes.filter(vote__total_plus__gte=80)
print(all_votes.values("vote").distinct().count(), "votes total")

counts = { }
class counter:
	def __init__(self): self.value = 0
	def inc(self): self.value += 1

for v in all_votes\
	.select_related('person')\
	.select_related('option'):
	counts.setdefault(v.person_id, {}).setdefault(v.option.key, counter()).inc()
	counts.setdefault(v.person_id, {}).setdefault('first', v.created)
	counts.setdefault(v.person_id, {})['last'] = v.created
	counts.setdefault(v.person_id, {})['person'] = v.person

# Clean / Sort
for p, v in counts.items():
	v["+"] = v.get("+", counter()).value
	v["-"] = v.get("-", counter()).value
counts = sorted(counts.items(), key = lambda kv : -kv[1]['-'])

# Write out.
writer = csv.writer(sys.stdout)
writer.writerow([
	"person",
	"name",
	"first vote",
	"last vote",
	"yea",
	"nay",
	])
for person, counts in counts:
	writer.writerow([
		person,
		counts['person'].name.encode("utf8"),
		counts['first'],
		counts['last'],
		counts['+'],
		counts['-']])

from vote.models import *
votecount = 0
counts = {False: 0, True: 0}
for y in (2009, 2010, 2011):
 for v in Vote.objects.filter(source=VoteSource.senate, created__year=y, category=VoteCategory.passage):
  if v.related_bill == None or v.related_bill.sponsor == None: continue
  p = v.related_bill.sponsor.get_role_at_date(v.created).party
  if p == "Independent": continue
  votecount += 1
  for vv in v.voters.exclude(person=None):
   r = vv.person.get_role_at_date(v.created)
   if vv.option.key in ("+", "-") and r and r.party != "Independent":
    counts[(r.party == p) ^ (vv.option.key == "-")] += 1
print(votecount, "votes")
print(float(counts[True])/sum(counts.values()))

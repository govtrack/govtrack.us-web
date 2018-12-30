#!script
from vote.models import Vote, CongressChamber

# Get votes on passage that succeeded.
votes = Vote.objects.filter(session__gte=2017)
votes = [
  v for v in votes
  if v.is_on_passage
 and v.total_plus > v.total_minus]

# Load the dem percentage for each vote.
for vote in votes:
	vote.totals = vote.totals()
	di = vote.totals["parties"].index("Democrat")
	ri = vote.totals["parties"].index("Republican")
	dpct = vote.totals["party_counts"][di]["yes"] / vote.totals["party_counts"][di]["total"]
	rpct = vote.totals["party_counts"][ri]["yes"] / vote.totals["party_counts"][ri]["total"]
	vote.dr = dpct / rpct

# Filter out votes that don't have a higher proportion of Dems
# voting in favor than the proportion of Republicans.
votes = [ v for v in votes if v.dr >= 1 ]
	
## Sort and show.
#votes.sort(key = lambda v : v.dr)
#for v in votes:
#	print(v.dr, "https://www.govtrack.us"+v.get_absolute_url(), v)

# Group by bill.
bills = { }
for vote in votes:
	bills.setdefault(vote.related_bill, {
		"bill": vote.related_bill,
	})
	bills[vote.related_bill][CongressChamber.by_value(vote.chamber).key] = vote

# Show bills in a helpful order.
bills = sorted(bills.values(), key = lambda b: (
	b["bill"].was_enacted_ex() is not None, # put all enacted bills together
	("senate" in b and "house" in b), # bills that have votes in both chambers
	((b["senate"].dr if "senate" in b else 0) + (b["house"].dr if "house" in b else 0)), # order by the ratio
))
for b in bills:
	print(
		b['bill'].title[0:30],
		b['bill'].was_enacted_ex() is not None,
		(b["senate"].dr if "senate" in b else None),
		(b["house"].dr if "house" in b else None),
		"https://www.govtrack.us"+b['bill'].get_absolute_url(),
		("https://www.govtrack.us"+b['senate'].get_absolute_url() if "senate" in b else ""),
		("https://www.govtrack.us"+b['house'].get_absolute_url() if "house" in b else "")
	)

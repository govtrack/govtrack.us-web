#!script

# Compares the votes of two or more Members of congress, possibly across chambers
# by looking at votes on bill passage.

import sys, csv

from bill.models import *
from person.models import *
from vote.models import *

# Pass person IDs on the command line.
people = [Person.objects.get(id=id) for id in sys.argv[1:]]

# Write header.
writer = csv.writer(sys.stdout)
headers = []
for p1 in people:
	headers.extend([ "%s date" % p1.lastname, "%s description" % p1.lastname, "%s url" % p1.lastname, "%s" % p1.name])
writer.writerow(headers)

# Look at all votes that any of the people participated in.
seen_votes = set()
for v1_id in Voter.objects.filter(person__in=people).values_list('vote', flat=True).order_by('created').distinct():
	if v1_id in seen_votes: continue
	v1 = Vote.objects.get(id=v1_id)

	# If this vote is on the passage of a bill, we can compare with other votes on
	# the passage of the bill.
	votes = [v1]
	passage_categories = (VoteCategory.passage, VoteCategory.passage_suspension)
	if v1.category in passage_categories:
		# Get the related bill and all "identical" companion bills.
		related_bills = set(rb.related_bill for rb in RelatedBill.objects.filter(bill=v1.related_bill).filter(relation="identical").select_related("related_bill"))
		votes.extend(list(Vote.objects.filter(related_bill__in=related_bills, category__in=passage_categories)))
		for v in votes: seen_votes.add(v.id)

	# Compute row.
	row = [ ]
	vote_keys = set()
	vote_ids = set()
	for p in people:
		# Find how p voted on any of these votes.
		try:
			v = Voter.objects.select_related('vote', 'option').get(person=p, vote__in=votes)
		except Voter.DoesNotExist:
			row.extend(["", "", "", "-not eligible-"])
			continue
	
		# Add person's vote to row.
		row.extend([
			v.vote.created.strftime("%x"),
			v.vote.question.encode("utf8"),
			"https://www.govtrack.us"+v.vote.get_absolute_url(),
			v.option.value,
		])

		# Record unique list of option keys.
		if v.option.key in ("+", "-"):
			vote_keys.add(v.option.key)

		vote_ids.add(v.vote.id)

	# Flag the number of different actual roll call votes involved in this comparison.
	row.append("" if len(vote_ids) == 1 else "(different votes)")

	if len(vote_keys) > 1:
		# Write row if the people didn't all vote the same way.
		writer.writerow(row)


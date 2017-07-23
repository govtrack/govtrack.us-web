#!script
# Find all Election of the Speaker votes.

from django.db.models import Count
from vote.models import Vote

# Look for likely Election of the Speaker votes. These appear in various ways
# throughout history, so filter out votes that are associated with bills and
# votes that have "Aye" choices, which could never be Speaker votes.
for vote in Vote.objects.filter(question__icontains="Speaker", related_bill=None).order_by('-created')\
	.exclude(options__key="+"):

	# What were the vote totals?
	counts = vote.voters.all().values("option__value").annotate(count=Count('id')).order_by('-count')
	options = "; ".join(
		"%s, %d" % (choice['option__value'], choice['count'])
		for choice in counts
		)

	# Find the presumed winner by the maximum vote.
	winner = counts[0]["option__value"]

	# Find the parties of those that voted for the winner. Then take
	# the sum of the votes from all but the first (highest count)
	# party.
	parties = vote.voters.filter(option__value=winner).values("person_role__party").annotate(count=Count('id')).order_by('-count')
	cross_party_votes = sum(party['count'] for party in parties[1:])

	print """
<!-- %s -->
<tr><td><a href="%s">%s</a></td> <td>%s</td> <td>%s</td> <td><a href="%s">%s</a></td></tr>
""" % (
	vote.question,
	"https://www.govtrack.us" + vote.get_absolute_url(),
	vote.created.year,
	options,
	cross_party_votes,
	vote.get_source_link(),
	vote.get_source_display(),
	)

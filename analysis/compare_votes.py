#!script

# Compares the votes of two or more Members of Congress, when they all
# voted on the same things.

import sys, csv

from person.models import *
from vote.models import *

# Pass person IDs on the command line.
people = [Person.objects.get(id=id) for id in sys.argv[1:]]

# Write header.
writer = csv.writer(sys.stdout)
writer.writerow(["date", "description", "url"] + [p.name.encode("utf8") for p in people])

# Get the votes of the first person, in order. We'll use this to order the output
# and to output vote metadata.
votes = Vote.objects.filter(voters__person=people[0]).order_by('created')

# Map each person to a mapping from all votes they participated in to how they
# voted on it (a VoteOption id).
pvotes = {
	p: {
		vote_id: option_id
		for vote_id, option_id in Voter.objects.filter(person=p).exclude(option__key="0").values_list('vote', 'option')
	}
	for p in people
}

# Filter down the votes to those that all people voted in. We repeat person[0]
# because the not-voting filter is applied only in pvotes but not in votes.
for p in people:
	votes = filter(lambda v : v.id in pvotes[p], votes)

# Load all of the option objects in bulk and turn into a mapping from ids to objects.
options = VoteOption.objects.filter(id__in=sum([pv.values() for pv in pvotes.values()], []))
options = { option.id: option for option in options }

# Loop over the votes that all of the people participated in.
counts = { }
for vote in votes:
	# Output a row.
	row = [vote.created.strftime("%x"),
		   vote.question.encode("utf8"),
		   "https://www.govtrack.us"+vote.get_absolute_url()]
	for p in people:
		option_id = pvotes[p][vote.id]
		row.append(options[option_id].value)
	writer.writerow(row)

	# Count up how many times each pair voted the same way.
	for p1 in people:
		for p2 in people:
			if p1.id >= p2.id: continue # skip same (==), do pairs once (>)
			if options[pvotes[p1][vote.id]].key in ("+", "-") and options[pvotes[p2][vote.id]].key in ("+", "-"):
				counts[(p1,p2,"TOTAL")] = counts.get((p1,p2,"TOTAL"), 0) + 1
				if pvotes[p1][vote.id] == pvotes[p2][vote.id]:
					counts[(p1,p2,"SAME")] = counts.get((p1,p2,"SAME"), 0) + 1

# Output totals (to stderr so it doesn't conflict with csv output).
sys.stderr.write(str(len(votes)) + " votes\n")
sys.stderr.write("voted the same way:\n")
for p1, p2, count_type in sorted(counts):
	if count_type == "TOTAL": continue # don't dup
	numerator = counts[(p1,p2,"SAME")]
	denominator = counts[(p1,p2,"TOTAL")]
	pct = round(numerator/float(denominator) * 100 * 10) / 10
	sys.stderr.write(p1.name.encode("utf8") + "\t" + p2.name.encode("utf8") + "\t" + str(numerator) + "\t" + str(denominator) + "\t" + str(pct) + "%\n")

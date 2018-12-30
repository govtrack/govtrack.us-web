#!script

# Look at whether the proportion of yes-voters in passed Senate votes matches
# the proportion of the population they represent.

import csv
import sys

from collections import defaultdict
from vote.models import Vote, Voter, CongressChamber, VoteCategory

def percent(value): return round(value*100, 1)

# Load historical state populations.
state_pop = { }
for state, year, pop in csv.reader(open("../historical_state_population_by_year.csv")):
	year = int(year)
	pop = int(pop)
	state_pop[(state, year)] = pop

# Write headers.
W = csv.writer(sys.stdout)
W.writerow(["date", "chamber", "category", "question", "yea_voters", "yea_pop", "yea_of_all_legislators", "link"])

# Process each vote.
for vote in Vote.objects\
	.filter(
		total_plus__gt=0, # votes without ayes are not relevant
		chamber=CongressChamber.senate, # in the senate
		category__in=(VoteCategory.passage, VoteCategory.nomination), # on the passage of bills and nominations
	)\
	.order_by('-created'):

	# Subtract 1 from the year because for 2018 votes we don't
	# have 2018 population yet.
	pop_year = vote.created.year - 1

	# Get how everyone voted.
	votes = vote.voters.all()\
		.values_list("option__key", "person_role__state", "person__id")

	# Count up the number of legislators for each state.
	legislators_per_state = defaultdict(lambda : 0)
	for _, state, _ in votes:
		legislators_per_state[state] += 1

	# Sum up the total population represented by each vote option # (i.e. yes/no),
	# apportioning the population of each state evenly across the legislators representing
	# that state who voted. Also just count total yes/no/not voting votes.
	pop_by_option = defaultdict(lambda : 0)
	count_by_option = defaultdict(lambda : 0)
	for option, state, personid in votes:
		if state == "": continue # Vice President's tie-breaker
		if (state, pop_year) not in state_pop: continue # one of the island territories, for which we don't have population data
		pop_by_option[option] += state_pop[(state, pop_year)] / legislators_per_state[state]
		count_by_option[option] += 1

	# Skip votes where the ayes were in the minority. Those votes represent failed outcomes. We're
	# only interested in the legitimacy of actual outcomes.
	if "+" not in pop_by_option or count_by_option["+"] < count_by_option.get("-", 0):
		continue

	# get the % of yes voters and % of the country's population represented by those voters
	count_percent_yea = count_by_option["+"]/(count_by_option["+"] + count_by_option.get("-", 0))
	pop_percent_yea = pop_by_option["+"]/(pop_by_option["+"] + pop_by_option.get("-", 0)) # of those voting
	pop_percent_yea_of_total = pop_by_option["+"]/sum(pop_by_option.values()) # of sworn senators

	# print
	W.writerow([vote.created.isoformat(), vote.chamber_name, VoteCategory.by_value(vote.category).key, str(vote), percent(count_percent_yea), percent(pop_percent_yea), percent(pop_percent_yea_of_total), "https://www.govtrack.us"+vote.get_absolute_url()])

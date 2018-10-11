#!script

import csv
import sys

from collections import defaultdict
from vote.models import Vote, Voter

# Load historical state populations.
state_pop = { }
for state, year, pop in csv.reader(open("../historical_state_population_by_year.csv")):
	year = int(year)
	pop = int(pop)
	state_pop[(state, year)] = pop

# Process each vote.
#winner = None
W = csv.writer(sys.stdout)
for vote in Vote.objects\
	.filter(total_plus__gt=0, total_minus__gt=0)\
	.order_by('-created'):

	# Subtract 1 from the year because for 2018 votes we don't
	# have 2018 population yet.
	pop_year = vote.created.year - 1

	# Force using 1900 population to test if this is about population change.
	pop_year = 1900

	# Get how everyone voted.
	votes = vote.voters.all()\
		.values_list("option__key", "person_role__state", "person__id")

	# Count up the number of legislators for each state.
	legislators_per_state = defaultdict(lambda : 0)
	for _, state, _ in votes:
		legislators_per_state[state] += 1

	# Sum up the total population represented by each vote option # (i.e. yes/no),
	# splitting the population of each state by the number of legislators representing
	# that state. Use the previous year's population count since we don't have 2018
	# population data yet. Also count up the vote totals so we can compare.
	pop_by_option = defaultdict(lambda : 0)
	count_by_option = defaultdict(lambda : 0)
	for option, state, personid in votes:
		if state == "": continue # Vice President's tie-breaker
		if (state, pop_year) not in state_pop: continue # one of the island territories, for which we don't have population data
		#if personid in (300075, 412549): option = "0" # Daines, Murkowski
		#if personid == 412533: option = ("+" if option == "-" else "-") # flip
		pop_by_option[option] += state_pop[(state, pop_year)] / legislators_per_state[state]
		count_by_option[option] += 1

	if "+" in pop_by_option and "-" in pop_by_option and count_by_option["+"] > count_by_option["-"]:
		count_percent_yea = round(100*count_by_option["+"]/(count_by_option["+"] + count_by_option["-"]), 1)
		pop_percent_yea = round(100*pop_by_option["+"]/(pop_by_option["+"] + pop_by_option["-"]), 1)
		pop_percent_yea_of_total = round(100*pop_by_option["+"]/sum(pop_by_option.values()), 1)

		#if not winner or pop_percent_yea < winner[1]:
		#	winner = (vote, pop_percent_yea)
		W.writerow([vote.created.isoformat(), vote.chamber_name, count_percent_yea, pop_percent_yea, pop_percent_yea_of_total, vote, vote.get_absolute_url()])

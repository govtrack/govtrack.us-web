#!script

# Look at whether the proportion of yes-voters in passed Senate votes matches
# the proportion of the population they represent. This script merely extracts
# the votes.

import csv
import sys
import tqdm

from collections import defaultdict
from vote.models import Vote, Voter, CongressChamber, VoteCategory
from person.models import PersonRole, RoleType

def percent(value): return round(value*100, 2)

# Historical total U.S. population.
# U.S. Census, 2010 Census, Population and Housing Unit Counts, Table 2
# https://www2.census.gov/library/publications/decennial/2010/cph-2/cph-2-1.pdf
us_pop = { 2020: 330317527, # NOTE: This data point from https://www.census.gov/popclock/
           2010: 308745538,
           2000: 281424603,
           1990: 248718302,
           1980: 226542199,
           1970: 203302031,
           1960: 179323175,
           1950: 151325798,
           1940: 132164569,
           1930: 123202624,
           1920: 106021537,
           1910: 92228496,
           1900: 76212168 }
def us_pop_at(year):
	# Interpolate or extrapolate.
	dec1 = year // 10 * 10 # decade at or before year
	dec2 = dec1 + 10 # decade after
	dec2 = min(dec2, max(us_pop.keys())) # limit to max data year
	dec1 = dec2 - 10 # if dec2 was limited to max data year, move dec1 to prior decade
	r = (year - dec1) / (dec2 - dec1)
	# Linearly interpolate or extrapolate.
	return (1-r)*us_pop[dec1] + r*us_pop[dec2]

# Load historical state populations.
state_pop = { }
for state, year, pop in csv.reader(open("analysis/historical_state_population_by_year.csv")):
	year = int(year)
	pop = int(pop)
	state_pop[(state, year)] = pop
state_pop_max_year = max(year for (state, year) in state_pop.keys())

# Write headers.
W = csv.writer(sys.stdout)
W.writerow(["congress", "session", "date", "category", "question", "yea_senators", "yea_statespop", "yea_uspop", "link"])

# Process each vote.
for vote in tqdm.tqdm(list(Vote.objects\
	.filter(
		total_plus__gt=0, # votes without ayes are not relevant
		chamber=CongressChamber.senate, # in the senate
		congress__gte=57, # first Congress than began after 1900 when we first have pop data
	)\
	.order_by('-created'))):

	pop_year = vote.created.year

	# Get how everyone voted. Exclude some data errors where voters are not tied to roles.
	votes = vote.voters.all()\
		.exclude(person_role=None)\
		.values_list("option__key", "person_role__state", "person__id")

	# Count up the number of voting legislators for each state,
	voting_legislators_per_state = defaultdict(lambda : 0)
	for option, state, _ in votes:
		if option not in ("+", "-"): continue # we only care about voting legislators
		voting_legislators_per_state[state] += 1

	# Get the state populations in the year of the vote. For this year's votes, we don't have
	# state populations yet, so just use the last year we have.
	state_pop_year = { state: pop for (state, year), pop in state_pop.items() if year == min(pop_year, state_pop_max_year) }

	# Sum up the total population in states with senators (i.e. real states at the time of the vote).
	all_states = set(state for _, state, _ in votes if state != "")
	state_pop_total = sum(state_pop_year[state] for state in all_states)

	# Get the total U.S. population in this time. Interpolate (or beyond the last year, extrapolate).
	country_population = us_pop_at(pop_year)

	# Sum up the total population represented by each vote option # (i.e. yes/no),
	# apportioning the population of each state evenly across the legislators representing
	# that state who voted. Also just count total yes/no/not voting votes.
	pop_by_option = defaultdict(lambda : 0)
	count_by_option = defaultdict(lambda : 0)
	for option, state, personid in votes:
		if state == "": continue # Vice President's tie-breaker
		if option not in ("+", "-"): continue # we only care about voting legislators
		pop_by_option[option] += state_pop_year[state] / voting_legislators_per_state[state]
		count_by_option[option] += 1

	# Skip votes where the ayes were in the minority. Those votes represent failed outcomes. We're
	# only interested in the legitimacy of actual outcomes.
	if "+" not in pop_by_option or count_by_option["+"] < count_by_option.get("-", 0):
		continue

	# get the % of yes voters out of senators voting and out of the country's population as a whole
	count_percent_yea = count_by_option["+"] / (count_by_option["+"] + count_by_option.get("-", 0))
	statepop_percent_yea = pop_by_option["+"] / state_pop_total
	uspop_percent_yea = pop_by_option["+"] / country_population

	# print
	W.writerow([vote.congress, vote.session if len(vote.session) == 4 else vote.created.year, vote.created.isoformat(),
	            VoteCategory.by_value(vote.category).key, str(vote),
	            percent(count_percent_yea), percent(statepop_percent_yea), percent(uspop_percent_yea),
	            "https://www.govtrack.us"+vote.get_absolute_url()])

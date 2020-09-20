#!script

# Compute the proportion of the population represented by senators in a
# hypothetical vote described in command-line arguments.

import sys
import csv
from collections import defaultdict
from person.models import PersonRole, RoleType

def percent(value): return round(value*100, 2)

pop_year = 2019
country_population = 328239523 # https://www.census.gov/newsroom/press-releases/2019/popest-nation.html

# Load state populations for the most recent year we have data.
state_pop = { }
for state, year, pop in csv.reader(open("analysis/historical_state_population_by_year.csv")):
  year = int(year)
  pop = int(pop)
  if year == pop_year:
    state_pop[state] = pop

# Get the list of all eligible-to-vote (currently serving) senators.
all_voters = set(PersonRole.objects.filter(current=True, role_type=RoleType.senator))

# Sum up the total population in states with senators (i.e. U.S. population excluding territories).
all_states = set(p.state for p in all_voters)
state_pop_total = sum(state_pop[state] for state in all_states)

# Get the list of aye voters from the command line.
aye_voters = set()
for s in sys.argv[1:]:
  add_remove = "add"
  if s.startswith("-"):
    add_remove = "remove"
    s = s[1:]
  if s in ("D", "R"):
    voters = set( PersonRole.objects.filter(current=True, party__startswith=s, role_type=RoleType.senator) )
  else:
    voters = { PersonRole.objects.get(current=True, person__id=s) }

  if add_remove == "add":
    aye_voters |= voters
  else:
    aye_voters -= voters

print(len(aye_voters), "/", len(all_voters))

# Count up the number of voting legislators for each state
# (i.e. if there are vacancies, a senator voting no takes
# their whole state's population),
voting_legislators_per_state = defaultdict(lambda : 0)
for p in all_voters:
  voting_legislators_per_state[p.state] += 1

# Compute the population of the aye voters. If senators split,
# allocate half to the aye population.
aye_population = 0
for p in aye_voters:
  aye_population += state_pop[p.state] / voting_legislators_per_state[p.state]

# get the % of yes voters out of senators voting and out of the country's population as a whole
statepop_percent_yea = aye_population / state_pop_total
uspop_percent_yea = aye_population / country_population

print(percent(statepop_percent_yea))
print(percent(uspop_percent_yea))

#print(sorted([(state_pop[p.state], p.person.id) for p in aye_voters]))


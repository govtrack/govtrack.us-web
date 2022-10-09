#!script

import tqdm
from bill.models import Bill
from person.models import Person, PersonRole, get_person_name
from haystack.query import SearchQuerySet

# Get all bills enacted, including via text incorporation,
# by current Members of Congress in their lifetime of service.
#people = Person.objects.filter(roles__current=True)
congress_numbers = [ 114, 115, 116 ]
sq = SearchQuerySet().using("bill").filter(
  indexed_model_name__in=["Bill"],
  enacted_ex=True,
  congress__in=congress_numbers)
  #sponsor__in=people.values_list("id", flat=True))

# Get legislators serving in this Congress.
from us import get_congress_dates
people = { }
roles = PersonRole.objects.filter(
    role_type=2,
    enddate__gt=get_congress_dates(congress_numbers[0])[0],
    startdate__lt=get_congress_dates(congress_numbers[-1])[1])
for role in roles:
    # Attach the role so the name is generated with the
    # right district number.
    if role.person in people:
        people[role.person]._roles.add(role)
    else:
        role.person._roles = { role }
        people[role.person] = role.person
assert len([r for r in roles if
    not (set(congress_numbers) & set(r.congress_numbers()))]) == 0

# Count up bills by sponsor. Exclude bills that were vehicles
# for passage. Ensure every legislator has an entry so we don't
# skip legislators with no bills enacted.
counts = { }
for p in people:
  counts[p] = 0
bills = Bill.objects\
    .select_related("sponsor")\
    .in_bulk([sr.pk for sr in sq]).values()
for bill in bills:
  if bill.original_intent_replaced is True: continue
  if bill.sponsor not in counts: continue # we filtered out senators
  counts[bill.sponsor] += 1

# Output from most to fewest.
for sponsor, count in sorted(counts.items(), key = lambda kv : -kv[1]):
  print(get_person_name(sponsor) + "\t" + str(count))


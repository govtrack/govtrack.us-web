#!script

import tqdm
from person.models import Person
from haystack.query import SearchQuerySet

# Get all bills enacted, including via text incorporation,
# by current Members of Congress in their lifetime of service.
current_mocs = Person.objects.filter(roles__current=True)
sq = SearchQuerySet().using("bill").filter(
  indexed_model_name__in=["Bill"],
  enacted_ex=True,
  sponsor__in=current_mocs.values_list("id", flat=True))

# Count up bills by sponsor. Exclude bills that were vehicles
# for passage. Ensure every current Member has an entry.
counts = { }
for p in current_mocs:
  counts[p] = 0
for sr in tqdm.tqdm(sq):
  bill = sr.object
  if bill.original_intent_replaced is True: continue
  counts[bill.sponsor] += 1

for sponsor, count in sorted(counts.items(), key = lambda kv : -kv[1]):
  print sponsor.name.encode("utf8") + "\t" + str(count)


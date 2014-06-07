#!script
from us import stateapportionment
from person.views import get_district_bounds_query

db = {}
for state in stateapportionment:
 db[(state,None)] = get_district_bounds(state, None)
 print state, db[(state,None)]
for state, numdists in stateapportionment.items():
 if numdists in (1, "T"): continue
 for dist in range(1, numdists+1):
  db[(state,dist)] = get_district_bounds(state, dist)
  print state, dist, db[(state,dist)]

import json
with open("person/district_bounds.json", "w") as f:
 f.write(json.dumps(dict( (("%s:%d" % k) if k[1] else k[0], "|".join(str(c) for c in v)) for k,v in db.items() ), indent=True, sort_keys=True))

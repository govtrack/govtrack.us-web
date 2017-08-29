#!script
# Analyze which MoCs GovTrack users are tracking and determine if
# district demographics or MoC demographics are factors.
#
# Pull recent tracked MoCs:
#
# ../../mysql.sh -Be 'select count(*) as n, feedname from events_subscriptionlist_trackers left join events_feed on feed_id=events_feed.id where feedname like "p:%" and date_added>"2017-01-03" group by feedname order by n desc;' > analysis/ptrackerscount.csv

import csv

from person.models import Person, RoleType

for row in csv.DictReader(open("analysis/ptrackerscount.csv"), delimiter="\t"):
  count = int(row["n"])
  person = Person.objects.get(id=row["feedname"].split(":")[1])
  role = person.get_current_role()
  if role is None or role.role_type not in (RoleType.representative, RoleType.senator): continue
  print(count, person, role)

#!script

from datetime import date, datetime, timedelta

import sys
import csv
import tqdm

from person.models import PersonRole, RoleType

# start and end date rage
date = date(2017, 1, 3)
end_date = datetime.now().date()

# Get date sequence.
dates = []
while date <= end_date:
  dates.append(date)
  date += timedelta(days=1)

# iterate over days
for i, date in tqdm.tqdm(list(enumerate(dates))):
  # Get total membership of each chamber on this date.

  # Find all terms that were valid on this date.
  by_office = { }
  for p in PersonRole.objects.filter(
    startdate__lte=date,
    enddate__gte=date,
  ).order_by('startdate'):
    # In case of a resignation and swearing in for the
    # same position on the same day, record all of the roles
    # that were found for each office on this day.
    by_office.setdefault(p.get_office_id(), []).append(p)

  # IF any office had more than one term valid on the date,
  # skip this date.
  if len([0 for roles in by_office.values() if len(roles) > 1]) > 1:
    dates[i] = (date, { "error": "time ambiguity" })

  # Ok, count by party.
  else:
    by_party = { }
    for office_roles in by_office.values():
      role = office_roles[0]
      party = role.get_party_on_date(date)
      key = RoleType.by_value(role.role_type).key + " - " + party
      by_party[key] = by_party.get(key, 0) + 1
    dates[i] = (date, by_party)

# Get an ordering of columns.
columns = sorted(set(
  sum([list(counts.keys()) for date, counts in dates], [])
  ))
w = csv.writer(sys.stdout)
w.writerow(["", "date"] + columns)
for i, (date, counts) in enumerate(dates):
  row = [i, date.isoformat()]
  for c in columns:
    row.append(counts.get(c, "-"))
  w.writerow(row)

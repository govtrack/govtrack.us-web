#!script

import csv, sys

from bill.models import Bill, Cosponsor
from person.name import get_person_name

bills = Bill.objects.filter(
  congress__gte=113,
  terms=5966, # Firearms and explosives
).select_related("sponsor", "sponsor_role")

qs = Cosponsor.objects.filter(
  withdrawn=None, # exclude withdrawn
  bill__in=bills,
).select_related("bill", "person", "role", "bill__sponsor", "bill__sponsor_role")

w = csv.writer(sys.stdout)

w.writerow([
  "congress",
  "bill number",
  "bill title",
  "bill's primary sponsor's party",
  "link",
  "sponsor/cosponsor",
  "person id",
  "person name (display)",
  "person name (sortable)",
  "person party",
  "sponsorship date",
])

def write_row(bill, sponsor, sponsor_type, sponsor_date):
  w.writerow([
    bill.congress,
    bill.display_number_no_congress_number,
    bill.title_no_number.encode("utf8"),
    bill.sponsor_role.party,
    "https://www.govtrack.us" + bill.get_absolute_url(),
    sponsor_type,
    sponsor.id,
    get_person_name(sponsor, firstname_position='before', show_district=True, show_party=True, firstname_style="nickname").encode("utf8"),
    get_person_name(sponsor, firstname_position='after', show_district=True, show_party=True, show_title=False, firstname_style="nickname").encode("utf8"),
    sponsor.role.party,
    sponsor_date.isoformat(),
  ])

for bill in bills:
  if bill.sponsor is None: continue
  bill.sponsor.role = bill.sponsor_role
  write_row(bill, bill.sponsor, "sponsor", bill.introduced_date)

for cosp in qs:
  cosp.person.role = cosp.role
  write_row(cosp.bill, cosp.person, "cosponsor", cosp.joined)

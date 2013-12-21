#!script

import sys, csv

from django.db.models import Count

from us import get_all_sessions
from person.models import *
from bill.models import *

def build(role_type, congress, session, session_start, session_end, people_sort_order, data_matrix):

	# Get all bills introduced in this congress and session by Members of
	# Congress in the desired chamber, aggregated by sponsor role.
	bill_counts = list(Bill.objects.filter(
			sponsor_role__role_type=role_type,
			congress=congress,
			introduced_date__gte=session_start,
			introduced_date__lte=session_end)\
			.values('sponsor_role')\
			.annotate(count=Count('sponsor_role')))

	# Get corresponding people.
	people_map = PersonRole.objects.in_bulk([ bc['sponsor_role'] for bc in bill_counts ])

	# add new people in sorted order by name
	people = list(set([r.person for r in people_map.values()]))
	if len(people_map) != len(people): raise ValueError() # sanity check that there is one role per person in this congress/chamber
	people.sort(key=lambda p : p.sortname)
	for p in people:
		if p not in data_matrix:
			people_sort_order.append(p)

	# build the output matrix
	for bc in bill_counts:
		data_matrix.setdefault(people_map[bc['sponsor_role']].person, {})[(congress, session)] = bc["count"]

	return len(bill_counts) > 0

for role_type in (RoleType.representative, RoleType.senator):
	people_sort_order = []
	data_matrix = { }
	sessions = []

	for congress, session, startdate, enddate in get_all_sessions():
		if congress < 109: continue # make a smaller table

		if build(role_type, congress, session, startdate, enddate, people_sort_order, data_matrix):
			print role_type.congress_chamber, congress, session
			sessions.append((congress, session))

	writer = csv.writer(open("sponsorship_counts_%s.csv" % role_type.congress_chamber, "w"))
	writer.writerow(["id", "name"] + [cs[1] for cs in sessions])

	def zero(value):
		if value is None: return 0
		return value

	for p in people_sort_order:
		writer.writerow(
			[p.id, p.sortname.encode("utf8")] + [str(zero(data_matrix[p].get(cs))) for cs in sessions]
			)

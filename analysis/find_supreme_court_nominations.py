#!script

import sys, csv, datetime

from person.models import PersonRole, RoleType
from vote.models import Vote

w = csv.writer(sys.stdout)
for v in Vote.objects\
	.filter(question__icontains="Supreme Court")\
	.filter(question__icontains="Nomination")\
	.order_by('created'):

	# who was president at the time of the vote?
	r = PersonRole.objects.filter(
		role_type=RoleType.president,
		startdate__lte=v.created,
		enddate__gte=v.created).first()

	# time till end of term-- because of deaths/resignations,
	# we can't use r.enddate. Compute forward from the vote date
	# to the next Jan 20 inaugural year.
	y = v.created.year
	if v.created.month == 1 and v.created.date < 20: y -= 1
	next_prez = datetime.date(y + 5-(y % 4), 1, 20)
	
	# write row
	w.writerow([
		# the vote
		v.id,
		v.created.isoformat(),
		v.question.encode("utf8"),
		v.total_plus,
		v.total_minus,
		v.total_other,

		# the president
		unicode(r.person).encode("utf8"),
	
		# days until the end of the current presidential term
		(next_prez - v.created.date()).days,

		#
		"https://www.govtrack.us" + v.get_absolute_url(),
		"https://www.govtrack.us" + v.get_absolute_url() + "/export/xml",
		"https://www.govtrack.us" + v.get_absolute_url() + "/export/csv",
		"https://www.govtrack.us" + v.get_absolute_url() + ".json",
	])



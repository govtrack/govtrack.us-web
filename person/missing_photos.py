#!script

import csv, sys

from person.models import Person

w = csv.writer(sys.stdout)

for p in Person.objects.filter(roles__current=True):
	if p.has_photo(): continue

#	# Does the unitedstates/images project have a dems.gov photo?
#	from urllib import urlopen
#	meta = urlopen("https://raw.githubusercontent.com/unitedstates/images/gh-pages/congress/metadata/%s.yaml" % p.bioguideid).read()
#	if "dems.gov" in meta:
#		print './manage.py import_photo %s %s http://www.dems.gov "House Democratic Caucus"' % (p.id, "https://raw.githubusercontent.com/unitedstates/images/gh-pages/congress/original/%s.jpg" % p.bioguideid)
#
#	continue

	w.writerow([
		p.bioguideid, p.id,
		p.name.encode("utf8"),
		p.current_role.website, "Office of " + p.name_no_details().encode("utf8"),
#		"https://raw.githubusercontent.com/unitedstates/images/gh-pages/congress/original/%s.jpg" % p.bioguideid,
#		"https://raw.githubusercontent.com/unitedstates/images/gh-pages/congress/metadata/%s.yaml" % p.bioguideid,
		])

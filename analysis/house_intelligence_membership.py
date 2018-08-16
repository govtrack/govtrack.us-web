#!script

import os.path, datetime, lxml.etree

from person.models import Person
from person.name import get_person_name
from committee.models import Committee

committee_code = 'SLIN' # Senate Intelligence

def person_name(id, when):
		p = Person.objects.get(id=id)
		p.role = p.get_role_at_date(when) # set for get_person_name
		return get_person_name(p)

for congress in range(109,114):
	# Load the historicla committee membership file for that Congress, which
	# should be a point-in-time snapshot somewhere within the Congress.
	fn = "data/historical-committee-membership/%d.xml" % congress
	file_save_date = datetime.datetime.fromtimestamp(os.path.getmtime(fn))
	cmte_mbrs = lxml.etree.parse(fn)

	# Iterate over all membership besides the target committee.
	memberships = { }
	for mbr in cmte_mbrs.findall("//committee/member"):
		cmte = mbr.getparent().get("code")
		if cmte == committee_code: continue
		memberships.setdefault(mbr.get("id"), set()).add(cmte)

	# Iterate over committee members.
	cross_seated = { }
	for mbr in cmte_mbrs.findall("//committee[@code='%s']/member" % committee_code):
		for cmte in memberships.get(mbr.get("id"), set()):
			cross_seated.setdefault(cmte, set()).add((mbr.get("id"), mbr.get("role")))

	print(congress, file_save_date)
	for cmte in sorted(cross_seated):
		print(Committee.objects.get(code=cmte).abbrev, "\t", \
			", ".join( person_name(id, file_save_date) + ((" (" + role + ")") if role else "") for (id, role) in sorted(cross_seated[cmte], key = lambda x : not x[1] ) ))
	print()

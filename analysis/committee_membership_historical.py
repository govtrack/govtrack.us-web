#!script

import glob, os.path, datetime, lxml.etree, csv, sys

from person.models import Person
from person.name import get_person_name
from committee.models import Committee

W = csv.writer(sys.stdout)

W.writerow([
	"congress",
	"as_of_date",
	"committee_code",
	"committee_name",
	"committee_abbrev",
	"role",
	"person_id",
	"person_name",
])

def person_name(p, when):
	p.role = p.get_role_at_date(when) # set for get_person_name
	return get_person_name(p).encode("utf8")

def dump_committee_membership(congress):
	# Load the historicla committee membership file for that Congress, which
	# should be a point-in-time snapshot somewhere within the Congress.
	fn = "data/historical-committee-membership/%d.xml" % congress
	file_save_date = datetime.datetime.fromtimestamp(os.path.getmtime(fn))
	cmte_mbrs = lxml.etree.parse(fn)

	# Iterate over all membership.
	for mbr in cmte_mbrs.findall("//committee/member"):
		cmte_code = mbr.getparent().get("code")
		cmte = Committee.objects.filter(code=cmte_code).first()
		person = Person.objects.get(id=mbr.get("id"))
		W.writerow([
			congress, file_save_date.date().isoformat(),
			cmte_code, cmte or "", (cmte and cmte.abbrev) or "",
			mbr.get("role") or "member",
			person.id,
			person_name(person, file_save_date)])

for congress in sorted([
	int(os.path.basename(fn)[:-4])
	for fn in
	glob.glob("data/historical-committee-membership/*.xml")]):
	dump_committee_membership(congress)

#!script

from person.models import PersonRole

for role in PersonRole.objects.filter(current=True).select_related('person'):
	p = role.person
	if not p.has_photo():
		print "perl pictures.pl IMPORT %d %s/... %s 'Office of %s'" % (p.id, role.website, role.website, p.name)
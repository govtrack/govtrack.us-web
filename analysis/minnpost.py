#!script

import csv, sys

from bill.models import *
from person.models import *

W = csv.writer(sys.stdout)
P = list(r.person for r in PersonRole.objects.filter(current=True, state="MN").order_by('role_type', 'district'))
P2 = P + list(r.person for r in PersonRole.objects.filter(current=True).exclude(state="MN").order_by('role_type', 'state', 'district'))

def u(obj):
	return str(obj).encode("utf8")
def write_col_headers(cols, rows):
	W.writerow(["", "<---", cols, "--->"])
	W.writerow([rows] + [u(p) for p in P])

write_col_headers("Sponsor", "Cosponsor")
for p1 in P2:
		W.writerow([u(p1)] + [Bill.objects.filter(
			sponsor=p2,
			cosponsors=p1,
			congress=113).count() for p2 in P])

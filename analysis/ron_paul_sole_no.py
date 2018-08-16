#!script

import sys, csv
from vote.models import Voter

sole_noes = Voter.objects.filter(person=400311, option__key="-", vote__total_minus=1).select_related("vote").order_by("created")
w = csv.writer(sys.stdout)
for nv in sole_noes:
	w.writerow([nv.vote.congress, nv.vote.session, nv.vote.created.isoformat(), str(nv.vote).encode("utf8"), "https://www.govtrack.us" + nv.vote.get_absolute_url()])

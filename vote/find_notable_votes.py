#!script

import sys, csv
from collections import defaultdict

from vote.models import Vote
from vote.views import get_vote_outliers, load_ideology_scores, attach_ideology_scores

writer = csv.writer(sys.stdout)
writer.writerow(["vote_id", "vote_url", "outliers"])

votes_to_process = Vote.objects.filter(created__gt='2015-01-01').order_by('created').values_list("id", flat=True)

for vid in votes_to_process:
    v = Vote.objects.get(id=vid)
    voters = v.get_voters()

    # attach ideology scores - used by get_vote_outliers
    attach_ideology_scores(voters, v.congress)

    # compute outliers
    get_vote_outliers(voters)
    outliers = { voter.person for voter in voters if getattr(voter, 'is_outlier', False) }
    if len(outliers) == 0: continue

    writer.writerow([v.id, v.get_absolute_url(), " ".join(str(p.id) for p in outliers)])

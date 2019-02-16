#!script

# Find all "key votes" in a Congress, which are votes that have a lot of statistical outliers.
# Write a CSV file listing the outliers of each vote so we can quickly determine what votes
# a MoC is an outlier or not an outlier in.
#
# (i.e. votes that are completely predictable are not interesting/informative for users trying
# to learn about their rep's record)

import sys
from collections import defaultdict

from vote.models import Vote
from vote.views import get_vote_outliers, load_ideology_scores, attach_ideology_scores

tqdm = lambda x : x
if sys.stdout.isatty():
    from tqdm import tqdm

congress = int(sys.argv[1])
votes_to_process = Vote.objects.filter(congress=congress).order_by('created').values_list("id", flat=True)
rows = []

for vid in tqdm(votes_to_process):
    v = Vote.objects.get(id=vid)
    voters = v.get_voters()

    # attach ideology scores - used by get_vote_outliers
    attach_ideology_scores(voters, v.congress)

    # compute outliers
    get_vote_outliers(voters)
    outliers = { voter.person for voter in voters if getattr(voter, 'is_outlier', False) }
    if len(outliers) == 0: continue
    rows.append([v.id, v.get_absolute_url(), " ".join(str(p.id) for p in outliers)])


import csv
writer = csv.writer(open("data/analysis/by-congress/%d/notable_votes.csv" % congress, "w"))
writer.writerow(["vote_id", "vote_url", "outliers"])
for row in rows:
    writer.writerow(row)


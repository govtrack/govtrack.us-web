#!.venv/bin/python
# Analyze the Senate legitimacy exported votes.

import sys
import csv
from collections import OrderedDict, defaultdict
import numpy

def run_analysis(grouper, analyzer):
  # Read the vote data and place into buckets.
  groups = OrderedDict()
  buckets = defaultdict(lambda : [])
  for vote in csv.DictReader(sys.stdin):
    vote["congress"] = int(vote["congress"])
    for field in ("yea_senators", "yea_statespop", "yea_uspop"): vote[field] = float(vote[field])
    g = grouper(vote)
    if g is None: continue # discard this vote
    groups[g] = g
    buckets[g].append(vote)

  # If the group is a tuple, how many elements are in the tuples?
  cat_cols = 1
  for g in groups:
    if isinstance(g, tuple):
      cat_cols = max(cat_cols, len(g))

  # Output. Since the data file is in reverse chronological order,
  # reverse the groups list.
  W = csv.writer(sys.stdout)
  W.writerow(["category_{}".format(i) for i in range(cat_cols)] + analyzer.columns)
  for g in reversed(groups):
    W.writerow(
      (list(groups[g]) if isinstance(groups[g], tuple) else [groups[g]])
      + analyzer(buckets[g])
    )

def group_by_congress(vote):
  y1 = 2019 + (vote["congress"] - 116) * 2
  return "{}-{}".format(y1, y1+1)

def group_by_session(vote):
  return vote["session"]

def group_by_session_and_vote_type(vote):
  vote_type = vote["category"]
  if vote_type == "unknown":
   if vote["question"].startswith("TO PASS"): vote_type = "passage"
   if "ON PASSAGE" in vote["question"]: vote_type = "passage"
   if vote["question"].startswith("TO CONFIRM THE NOMINATION OF"): vote_type = "nomination"
   if vote["question"].startswith("TO ADVISE AND CONSENT TO THE NOMINATION"): vote_type = "nomination"
   if vote["question"].startswith("CONFIRMATION OF"): vote_type = "nomination"
   if vote["question"].startswith("NOMINATION OF"): vote_type = "nomination"
   if "NOMINATION TO BE" in vote["question"]: vote_type = "nomination"
  if vote_type not in ("passage", "nomination"): vote_type = "other"
  return vote["session"], vote_type

def analyze_mean_values(votes):
  return [
    len(votes),
    numpy.mean([v['yea_senators'] for v in votes]),
    numpy.mean([v['yea_statespop'] for v in votes]),
    numpy.mean([v['yea_uspop'] for v in votes])
  ]
analyze_mean_values.columns = ["count", "mean_yea_senators", "mean_yea_statespop", "mean_yea_uspop"]

def analyze_mean_discrepancy(votes):
  return [len(votes),
          numpy.mean([
            v['yea_senators'] - v['yea_uspop']
            for v in votes
          ])]
analyze_mean_discrepancy.columns = ["count", "mean_discrep"]

def percent_of_minority_majority(votes):
  ## Print the most extreme case in the bucket.
  #v = min(votes, key = lambda v : v["yea_uspop"])
  #print(v)

  return [len(votes),
          numpy.mean([
            1 if v['yea_uspop'] <= 50 else 0
            for v in votes
          ])]
percent_of_minority_majority.columns = ["count", "pct_min_maj"]

run_analysis(group_by_congress, percent_of_minority_majority)

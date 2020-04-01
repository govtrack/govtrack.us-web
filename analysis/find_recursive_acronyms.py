import glob
import json
import re

# Iterate over all bills...
for fn in glob.glob("data/congress/11*/bills/*/*/data.json"):
  with open(fn) as f:
    bill = json.load(f)
  for title in bill.get("titles", []):
    title = title["title"]

    # Okay, now the fun part...

    # Does it start with a two-or-more capital letter sequence + space?
    m = re.match(r"^([A-Z]{2,})(.*?)( Act(?: of \d\d\d\d)?)?$", title)
    if not m: continue
    acronym, remainder, act_of_year = m.groups()
    remainder = remainder.strip()

    # The remainder must be at least as long as the acronym (after the first letter).
    if len(remainder) <= len(acronym)-1: continue

    # Does the potential acronym match the remainder of the title?
    # Each letter in the acronym, after the first (which matches the
    # acronym itself, if it's recursive) must match another letter
    # in the title. Normally it must match on capital letters, but
    # that's too strict. Every capital letter in the title must match,
    # and other lowercase letters and the "A" in "Act (of YYYY)" may
    # also be used to match.
    remainder_re = re.split("([A-Z])", remainder)
    remainder_re = [r for r in remainder_re if len(r.strip()) > 0]
    remainder_re = "".join(
      r if re.match("[A-Z]$", r)
      else "[" + "".join(re.escape(c) for c in r if c != " ") + "]*"
      for r in remainder_re
    )
    if re.match("^" + remainder_re + "A?$", acronym[1:], re.I):
      print(title)

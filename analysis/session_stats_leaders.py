#!script

import sys, json

from us import statenames
from person.models import Person, PersonRole

# adapted from views.py to be more suitable for twitter
def get_cohort_name(key):
    if key == "house": return "in the House"
    if key == "senate": return "in the Senate"
    if key == "party-house-democrat": return "of House Dems"
    if key == "party-house-republican": return "of House GOP"
    if key == "party-house-independent": return "of House Independents"
    if key == "party-senate-democrat": return "of Sen Dems"
    if key == "party-senate-republican": return "of Sen GOP"
    if key == "party-senate-independent": return "of Senate Independents"
    if key.startswith("house-state-delegation-"): return "of " + statenames[key[23:25].upper()] + " Delegation"
    if key == "house-leadership": return "of House Party Leaders"
    if key == "senate-leadership": return "of Senate Party Leaders"
    if key == "house-freshmen": return "of freshmen reps"
    if key == "senate-freshmen": return "of Senate freshmen"
    if key == "house-sophomores": return "of sophomore reps"
    if key == "senate-sophomores": return "of Senate sophomores"
    if key == "house-tenyears": return "of reps Serving 10+ Years"
    if key == "senate-tenyears": return "of sens Serving 10+ Years"
    if key == "house-committee-leaders": return "of House Cmte. Chairs/RkMembs"
    if key == "senate-committee-leaders": return "of Senate Cmte. Chairs/RkMembs"
    if key == "house-competitive-seat": return "of competitive House seats"
    if key == "house-safe-seat": return "of safe House seats"
    raise ValueError(key)

allstats = json.load(open(sys.argv[1]))
collected_stats = []
for id, stats in allstats["people"].items():
	person = Person.objects.get(id=id)
	if not person.roles.filter(current=True).exists(): continue # skip anyone no longer serving
	role = PersonRole.objects.get(id=stats["role_id"])
	for statname, statinfo in stats["stats"].items():
		if statname in ("bills-with-committee-leaders", "bills-with-companion", "committee-positions", "cosponsored-other-party"): continue

		if statname == "ideology" and (stats["stats"]["bills-introduced"]["value"] < 10 or stats["stats"]["leadership"]["value"] < .25): continue
		if statname == "leadership" and stats["stats"]["bills-introduced"]["value"] < 10: continue

		for cohortname, groupinfo in statinfo.get("context", {}).items():
			if cohortname in ("house-safe-seat", "house-tenyears", "senate-tenyears", "house-leadership", "senate-leadership", "house-committee-leaders", "senate-committee-leaders") or "delegation" in cohortname: continue
			if groupinfo["rank_ties"] > 1: continue
			if min(groupinfo["rank_ascending"], groupinfo["rank_descending"]) == 1:
				collected_stats.append( (person, role, statname, cohortname, groupinfo) )

collected_stats.sort(key = lambda x : (min(x[4]["rank_ascending"], x[4]["rank_descending"]) - x[4]["rank_ties"], x[4]["N"]), reverse=True)

seen = set()
for person, role, statname, cohortname, groupinfo in collected_stats:
	if (person, statname) in seen: continue
	seen.add( (person, statname) )

	tweet = ""

	if statname == "ideology":
		if groupinfo["rank_ascending"] == 1 and role.party == "Republican":
			tweet += "was the most moderate Repub"
		elif groupinfo["rank_ascending"] == 1:
			tweet += "was the most liberal"
		elif groupinfo["rank_descending"] == 1 and role.party == "Democrat":
			tweet += "was the most moderate Dem"
		elif groupinfo["rank_descending"] == 1:
			tweet += "was the most conservative"
		else:
			raise ValueError()

	elif statname == "leadership":
		if groupinfo["rank_ascending"] == 1:
			continue
		elif groupinfo["rank_descending"] == 1:
			tweet += "got our highest leadership score"

	elif statname == "cosponsors":
		if groupinfo["rank_ascending"] == 1:
			continue
		elif groupinfo["rank_descending"] == 1:
			tweet += "got the most cosponsors"

	elif statname == "bills-introduced":
		if groupinfo["rank_ascending"] == 1:
			continue
		elif groupinfo["rank_descending"] == 1:
			tweet += "wrote the most bills"

	elif statname == "bills-reported":
		if groupinfo["rank_ascending"] == 1:
			continue
		elif groupinfo["rank_descending"] == 1:
			tweet += "got the most bills out of committee"

	elif statname == "bills-enacted":
		if groupinfo["rank_ascending"] == 1:
			continue
		elif groupinfo["rank_descending"] == 1:
			tweet += "wrote the most new laws"

	elif statname == "bills-with-cosponsors-both-parties":
		if groupinfo["rank_ascending"] == 1:
			continue
		elif groupinfo["rank_descending"] == 1:
			tweet += "wrote the most bipartisan bills"

	elif statname == "cosponsored":
		if groupinfo["rank_ascending"] == 1:
			tweet += "cosponsored the fewest bills"
		elif groupinfo["rank_descending"] == 1:
			tweet += "cosponsored the most bills"

	elif statname == "missed-votes":
		if groupinfo["rank_ascending"] == 1:
			tweet += "missed the fewest votes"
		elif groupinfo["rank_descending"] == 1:
			tweet += "missed the most votes"

	elif statname == "transparency-bills":
		if groupinfo["rank_ascending"] == 1:
			continue
		elif groupinfo["rank_descending"] == 1:
			tweet += "got our highest #transparency score"

	else:
		superlative = "lowest" if groupinfo["rank_ascending"] == 1 else "highest"
		tweet += "has the " + superlative + " " + statname
	tweet += " "

	tweet += get_cohort_name(cohortname)

	if allstats["meta"]["is_full_congress_stats"]:
		tweet += " last Congress"
	else:
		tweet += " in " + str(allstats["meta"]["session"])

	if groupinfo["rank_ties"] > 0:
		tweet += " (tied w/ %d)" % groupinfo["rank_ties"]

	if person.twitterid and person.lastname.lower().replace(" ", "").replace("-", "") in person.twitterid.lower():
		if person.twitterid.lower().startswith("rep") or person.twitterid.lower().startswith("sen"):
			tweet = "Who " + tweet + "? It was @" + person.twitterid + "."
		else:
			tweet = role.get_title_abbreviated() + " @" + person.twitterid + " " + tweet + "."
	else:
		tweet = person.name_lastonly().encode("utf8") + " " + ("(@%s) " % person.twitterid if person.twitterid else "") + tweet + "."

	tweet += " More in our #govstats: "
	if len(tweet) > 120: print "TOO LONG:", # url below counts as 20 chars

	tweet += "https://www.govtrack.us" + person.get_absolute_url() + "/report-card/" + str(allstats["meta"]["session"])

	print tweet
	print

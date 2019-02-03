#!script

import sys, json, re

from us import statenames
from person.models import Person, PersonRole
from person.views_sessionstats import stat_titles, get_cohort_name

session = re.match(r".*-(\d\d\d\d)\.", sys.argv[1]).group(1)
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

	if person.twitterid and person.lastname.lower().replace(" ", "").replace("-", "") in person.twitterid.lower():
		if person.twitterid.lower().startswith("rep") or person.twitterid.lower().startswith("sen"):
			tweet = ".@" + person.twitterid
		else:
			tweet = role.get_title_abbreviated() + " @" + person.twitterid
	else:
		tweet = person.name_lastonly() + " " + ("(@%s) " % person.twitterid if person.twitterid else "")

	tweet += " "

	statinfo = stat_titles[statname]

	tweet += statinfo["verb"][0].lower() + " " + statinfo["verb"][1] + " "
	if groupinfo["rank_ascending"] == 1:
		tweet += statinfo["superlatives"][1]
	elif groupinfo["rank_descending"] == 1:
		tweet += statinfo["superlatives"][0]
	elif groupinfo["rank_ascending"] < group_info["rank_descending"]:
		tweet += "?th " + statinfo["superlatives"][1]
	else:
		tweet += "?th " + statinfo["superlatives"][0]
	tweet += " " + statinfo["verb"][2] + " "
	tweet = tweet.replace("  ", " ")

	tweet += "out of " + get_cohort_name(cohortname).replace("All ", "all ")

	if allstats["meta"]["is_full_congress_stats"]:
		tweet += " last Congress"
	else:
		tweet += " in " + str(allstats["meta"]["session"])

	if groupinfo["rank_ties"] > 0:
		tweet += " (tied w/ %d)" % groupinfo["rank_ties"]

	tweet += ". "
	tweet += "https://www.govtrack.us" + person.get_absolute_url() + "/report-card/" + session

	print(tweet)
	print()

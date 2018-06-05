#!script

import sys, csv
from vote.models import Vote, VoteCategory

all_votes = Vote.objects.filter(
	category=VoteCategory.nomination,
	created__gte="2009-01-20")

# What sorts of votes are these?
district_judges = 0
circuit_judges = 0
secretaries_ags = 0
fed_govs = 0
ambassadors = 0
boards_commissions = 0
sup_ct = 0
other = 0
for v in all_votes:
	if "District Judge" in v.question:
		district_judges += 1
	elif "Circuit Judge" in v.question:
		circuit_judges += 1
	elif "Justice of the Supreme Court" in v.question:
		sup_ct += 1
	elif "Secretary" in v.question or "Attorney General" in v.question or "Trade Representative" in v.question or "Solicitor General" in v.question\
			or "be Director of" in v.question or "be Commissioner of" in v.question or "to be Administrator of" in v.question:
		secretaries_ags += 1
	elif "Board of Governors of the Federal Reserve System" in v.question:
		fed_govs += 1
	elif "be Ambassador to" in v.question:
		ambassadors += 1
	elif "to be a Member of the" in v.question:
		boards_commissions += 1
	else:
		print(v.question)
		other += 1

print("district judges", district_judges)
print("circuit judges", circuit_judges)
print("supreme court", sup_ct)
print("senior agency positions", secretaries_ags)
print("federal reserve board of govs", fed_govs)
print("ambassadors", ambassadors)
print("boards and commissions", boards_commissions)
print("other (printed above)", other)

# Ordered by most no votes.
w = csv.writer(sys.stdout)
w.writerow(["date", "yeas", "nays", "nomination", "result", "link"])
for v in all_votes.order_by('-total_minus'):
	w.writerow([
		v.created.strftime("%x"),
		v.total_plus,
		v.total_minus,
		v.question,
		v.summary(),
		"https://www.govtrack.us" + v.get_absolute_url(),
	])

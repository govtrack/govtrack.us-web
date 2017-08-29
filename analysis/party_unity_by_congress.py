#!script

import sys, csv, tqdm

from vote.models import Vote, CongressChamber

votes = Vote.objects.filter(congress__range=(85, 100), chamber=CongressChamber.house).order_by('created')

stats = { }
party_grand_totals = { }

for vote in tqdm.tqdm(votes, total=votes.count()):
	totals = vote.totals()

	try:
		total_yes = [opt['count'] for opt in totals['options'] if opt['option'].key == "+"][0]
		total_no = [opt['count'] for opt in totals['options'] if opt['option'].key == "-"][0]
		overall_yes = total_yes / float(total_yes + total_no)
	except (IndexError, ZeroDivisionError):
		# There aren't yes/no options or there are (probably incorrectly) but neither had any votes.
		continue

	for party, party_totals in zip(totals["parties"], totals["party_counts"]):
		if party in ("Independent", "Vice President"): continue
		if party_totals['yes'] + party_totals['no'] > 0:
			year = stats.setdefault(vote.session, {})
			year_party = year.setdefault(party, [])
			value = max(party_totals['yes'], party_totals['no']) / float(party_totals['yes'] + party_totals['no'])
			weight = abs(party_totals['yes']/float(party_totals['yes'] + party_totals['no']) - overall_yes)
			year_party.append((value, weight))
			party_grand_totals[party] = party_grand_totals.get(party, 0) + party_totals['total']

party_list = sorted(party_grand_totals, key = lambda p : party_grand_totals[p], reverse=True)

w = csv.writer(sys.stdout)
w.writerow(["legyear"] + party_list)

def weighted_mean(a):
	total = float(sum(v[1] for v in a))
	if total == 0: return ""
	return sum(v[0] * v[1] for v in a) / total

for year, totals in sorted(stats.items()):
	w.writerow([year] + [weighted_mean(totals.get(party, [])) for party in party_list])
		

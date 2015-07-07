#!script

import csv
from bill.models import Bill, BillTerm
from bill.title import get_secondary_bill_title
from bill.billtext import load_bill_text

import logging
l = logging.getLogger('django.db')
l.setLevel(logging.DEBUG)
l.addHandler(logging.StreamHandler())

# Initialize output CSV files.
files = {
	(1, False): "old_subterms",
	(1, True): "old_topterms",
	(2, False): "new_subterms",
	(2, True): "new_topterms",
}
seen_bills = { }
for k, v in list(files.items()):
	files[k] = (
		csv.writer(open("data/misc/subject_terms_data/" + v + ".csv", "w")),
		csv.writer(open("data/misc/subject_terms_data/" + v + "_billtext.csv", "w")),
		csv.writer(open("data/misc/subject_terms_data/" + v + "_citations.csv", "w")),
		)
	files[k][0].writerow([
		"term",
		"bill_id",
		])
	files[k][1].writerow([
		"bill_id",
		"bill_title1",
		"bill_title2",
		"bill_date",
		"bill_sponsor_party",
		"bill_link",
		"bill_text",
		])
	files[k][2].writerow([
		"bill_id",
		"citation_id",
		])
	seen_bills[k] = set()

def get_secondary_bill_title_2(bill):
	t = get_secondary_bill_title(bill, bill.titles)
	if t is None: return ""
	return t

for t in BillTerm.objects.all().order_by('name'):
	k = (t.term_type, t.is_top_term())

	w1, w2, w3 = files[k]

	print t, t.term_type, t.is_top_term()

	for bill in Bill.objects.filter(congress__gte=108, terms=t).only("id", "congress", "bill_type", "number", "title", "titles", "introduced_date", "sponsor_role__party").prefetch_related("sponsor_role"):
		w1.writerow([
			t.name.encode("utf8"),
			bill.id,
			])

		if not bill.id in seen_bills[k]:
			seen_bills[k].add(bill.id)

			text = load_bill_text(bill, None, plain_text=True)
			w2.writerow([
				bill.id,
				bill.title_no_number.encode("utf8"),
				get_secondary_bill_title_2(bill).encode("utf8"),
				bill.introduced_date.isoformat(),
				bill.sponsor_role.party if bill.sponsor_role else "N/A",
				"https://www.govtrack.us" + bill.get_absolute_url(),
				text[0:4096].encode("utf8"),
				])

			for cite_id in sorted(bill.usc_citations_uptree()):
				w3.writerow([
					bill.id,
					cite_id,
					])


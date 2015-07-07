import glob, json, csv, sys

data = []
for f in glob.glob("data/congress/113/bills/*/*/data.json"):
	x1 = None
	x2 = None
	j = json.load(open(f))
	for axn in j['actions']:
		if axn.get('status') == 'PASSED:BILL':
			x1 = axn['acted_at']
		if axn.get('status') == 'ENACTED:SIGNED':
			x2 = axn['acted_at']
	if x1 or x2:
		data.append( (j['bill_id'], x1, x2) )

data.sort(key = lambda x : x[1] if x[1] else x[2])

w = csv.writer(sys.stdout)
w.writerow(["bill", "passed", "signed"])
for row in data:
	w.writerow(row)

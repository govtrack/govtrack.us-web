# Compare two session stats files but ignore the 'context' parts of each
# because it generates noisy diffs. And round some floats.
import sys, json, tempfile, os

def filter_stats(fn):
	data = json.load(open(fn))
	for p in data["people"].values():
		for stkey, st in p["stats"].items():
			if stkey in ("leadership", "ideology"):
				st["value"] = round(st["value"], 2)
			if "context" in st:
				del st["context"]
	return json.dumps(data, indent=2, sort_keys=True)

fn1, fn2 = sys.argv[1:3]

with tempfile.NamedTemporaryFile() as fp1:
	fp1.write(filter_stats(fn1))
	with tempfile.NamedTemporaryFile() as fp2:
		fp2.write(filter_stats(fn2))

		os.system("diff -u %s %s" % (fp1.name, fp2.name))

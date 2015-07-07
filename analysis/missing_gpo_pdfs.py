#!script

from bill.models import BillType

import glob, re, os.path

for congress in range(103, 112+1):
	for fn in glob.glob("data/us/bills.text/%d/*/*.xml" % congress):
		bill_type, bill_number, print_code, stuff = re.search(r"/([a-z]+)(\d+)([a-z][a-z0-9]*)?(\.gen|\.mods)?\.xml$", fn).groups()
		if not print_code: continue # my symbolic links to latest version
		if stuff: continue # ".gen".html
		bill_type = BillType.by_xml_code(bill_type).slug
		fn2 = "data/congress/%d/bills/%s/%s%s/text-versions/%s/mods.xml" % (
			congress, bill_type, bill_type, bill_number, print_code)
		if not os.path.exists(fn2):
			print fn2
		


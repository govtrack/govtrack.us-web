#!script
# Find all Wikipedia pages for bills in Congress, by
# looking for uses of the "Infobox U.S. legislation"
# template (https://en.wikipedia.org/wiki/Template:Infobox_U.S._legislation).
# There are less than 1,000 such pages.

import urllib.request, urllib.parse, urllib.error, json, re
import mwparserfromhell

from bill.models import Bill, BillSummary, BillType

# FUNCTIONS

def query(url):
	url = "https://en.wikipedia.org/w/api.php?format=json&" + url
	response = urllib.request.urlopen(url)
	return json.loads(response.read().decode("utf8"))

def get_pages_that_embed(template_name):
	continue_arg = None
	while True:
		# Construct next page for query results.
		url = "action=query&list=embeddedin&einamespace=0&eifilterredir=nonredirects&eilimit=500"
		url += "&eititle="  + urllib.parse.quote(template_name)
		if continue_arg:
			# every iteration but the first
			url += "&eicontinue=" + continue_arg

		# Fetch.
		results = query(url)
		for page in results["query"]["embeddedin"]:
			yield page
			#return # DEUBGGING, just get one

		# Iterate by getting the next 'eicontinue' parameter
		# from the response body.
		try:
			continue_arg = results["continue"]["eicontinue"]
		except KeyError:
			# No more results. Don't iterate more.
			break

def get_page_content(pages, params, limit, extractfunc):
	# Go in chunks.
	pages = list(pages) # clone
	while len(pages) > 0:
		# Shift off items.
		this_batch = pages[:limit]
		del pages[:limit]

		# Query.
		url = "action=query"
		url += "&" + params
		url += "&pageids=" + "|".join(str(page["pageid"]) for page in this_batch)
		contents = query(url)
		page_data = contents["query"]["pages"]
		assert len(page_data) == len(this_batch)

		# Update the dicts given in the pages argument with the
		# information we just queried.
		for page in this_batch:
			queried_page_data = page_data[str(page["pageid"])]
			page.update(extractfunc(queried_page_data))

def get_bill_for_page(page):
	for template in mwparserfromhell.parse(page["text"]).filter_templates():
		if template.name.strip() == "Infobox U.S. legislation":
			#print page["title"].encode("utf8")
			try:
				billref = get_bill_from_infobox(template)
			except Exception as e:
				print(page["pageid"], e)
				billref = None
			if billref:
				try:
					if billref[0] == "PL":
						# Get by pulic law number.
						return Bill.objects.get(congress=billref[1], sliplawpubpriv="PUB", sliplawnum=billref[2])
					elif billref[0] == "BILL":
						# It's a bill number.
						return Bill.objects.get(congress=billref[1], bill_type=BillType.by_slug(billref[2]), number=billref[3])
				except Bill.DoesNotExist:
					return None
	return None

def has_param(template, param):
	return template.has(param) \
	  and template.get(param).value.strip() \
	  and not template.get(param).value.strip().startswith("<!--") # could be overzealous

def get_bill_from_infobox(template):
	if has_param(template, "cite public law"):
		value = template.get("cite public law").value.strip()
		m = re.match("(?:p(?:ub(?:lic)?)?\.?\s*?l(?:aw)?.?\s*(?:no.?)?)?\s*(\d+)\s*[-\u2013\.]\s*(\d+)$", value, re.I)
		if m:
			return ("PL", int(m.group(1)), int(m.group(2)))
		m = re.match("\{\{USPL\|(\d+)\|(\d+)\}\}$", value, re.I)
		if m:
			return ("PL", int(m.group(1)), int(m.group(2)))
	if has_param(template, "leghisturl"):
		value = template.get("leghisturl").value.strip()
		m = re.match("http://(?:thomas.loc|www.congress).gov/cgi-bin/bdquery/z\?d(\d+):([a-z\.]+)(\d+):", value, re.I)
		if m:
			thomas_bill_types = { "H": "hr", "HR": "hr", "SN": "s", "S": "s" }
			return ("BILL", int(m.group(1)), thomas_bill_types[m.group(2).replace(".", "").upper()], int(m.group(3)))
		m = re.match("https?://(?:www|beta).congress.gov/bill/(\d+)\w+-congress/([\w-]+)/(\d+)", value)
		if m:
			congressgov_bill_types = { "house-bill": "hr", "senate-bill": "s", "house-resolution": "hres", "senate-resolution": "sres", "house-joint-resolution": "hjres", "senate-joint-resolution": "sjres", "house-concurrent-resolution": "hconres", "senate-concurrent-resolution": "sconres" }
			return ("BILL", int(m.group(1)), congressgov_bill_types[m.group(2)], int(m.group(3)))
		m = re.match("https://www.govtrack.us/congress/bills/(\d+)/([a-z]+)(\d+)", value)
		if m:
			return ("BILL", int(m.group(1)), m.group(2), int(m.group(3)))
	if has_param(template, "introducedbill"):
		value = template.get("introducedbill").value.strip()
		m = re.match(r"\{\{USBill\|(\d+)\|([\w\.]+)\|(\d+)\}\}$", value)
		if m:
			wikipedia_bill_type = { "S": "s", "HR": "hr", "H": "hr", "SJ": "sjres" }
			return ("BILL", int(m.group(1)), wikipedia_bill_type[m.group(2).replace(".", "").upper()], int(m.group(3)))
		if has_param(template, "enacted by"):
			congress = template.get("enacted by").value.strip()
			m = re.match("(\d+)", congress)
			if m:
				congress  = int(m.group(1))
				m = re.match("^([a-z\. ]+?)\s*(\d+)$", value, re.I)
				if m:
					textual_bill_type = { "S": "s", "HR": "hr", "SJ": "sjres" }
					mbt = m.group(1).replace(".", "").replace(" ", "").upper()
					if mbt in textual_bill_type:
						return ("BILL", congress, textual_bill_type[mbt], int(m.group(2)))
	return None

# Query for matching pages.
pages = list(get_pages_that_embed("Template: Infobox U.S. legislation"))

# Add text extracts of introductions.
get_page_content(pages, "prop=extracts&exlimit=max&exintro", 20, lambda page : { "extract": page["extract"] })

# And wikitext for each page.
get_page_content(pages, "prop=revisions&rvprop=content", 50, lambda page : { "text": page["revisions"][0]["*"] })

# For each Wikipedia page, figure out what bill it is about.
# Then collate by bill, in case multiple pages are about the
# same bill.
bill_summaries = { }
for page in pages:
	# Find the template.
	bill = get_bill_for_page(page)
	if bill:
		bill_summaries.setdefault(bill.id, []).append(page)
	#else:
	#	print(page["title"].encode("utf8"))

# Create/update BillSummary objects.
for bill_id, pages in bill_summaries.items():
	# There could be multiple pages for a single bill. Skip for those.
	if len(pages) != 1: continue

	# Is there an existing summary.
	bs = BillSummary.objects.filter(bill=bill_id).first()
	if bs:
		# Don't overwrite one that doesn't have a Wikipedia source.
		if bs.source_text != "Wikipedia":
			continue
	else:
		# Create a new instance.
		bs = BillSummary(bill_id=bill_id)
	
	# Update that instance and save if anything changed.
	page = pages[0]
	update_fields = {
		"source_text": "Wikipedia",
		"source_url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(page["title"].replace(" ", "_")),
		"content": page["extract"] + "\n\n<p>This summary is from <a href=\"%s\">Wikipedia</a>.</p>" % bs.source_url,
	}
	updated = False
	for k, v in list(update_fields.items()):
		if getattr(bs, k, None) != v:
			setattr(bs, k, v)
			updated = True
	if updated:
		bs.save()
		print(bs)
			

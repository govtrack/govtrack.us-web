if __name__ == "__main__":
	import sys, os
	sys.path.insert(0, "..")
	sys.path.insert(0, ".")
	sys.path.insert(0, "lib")
	sys.path.insert(0, ".env/lib/python2.7/site-packages")
	os.environ["DJANGO_SETTINGS_MODULE"] = 'settings'

import urllib, json

from bill.billtext import load_bill_text, parse_usc_citation
from bill.views import load_bill_from_url

# XXX: Modified from fetch_bill_index_json() in unitedstates/congress/tasks/deepbills.py
def fetch_deepbills_bill_index():
	return json.loads(urllib.urlopen("http://deepbills.cato.org/api/1/bills").read())

### MODS ###

def mods_metadata_for(deepbills_bill_version_id_parts):
	try:
		bill = load_bill_from_url(deepbills_bill_version_id_parts["congress"], deepbills_bill_version_id_parts["billtype"], deepbills_bill_version_id_parts["billnumber"])
	except django.http.response.Http404:
		return None

	try:
		metadata = load_bill_text(bill, deepbills_bill_version_id_parts["billversion"], mods_only=True)
	except IOError:
		return None

	return metadata

def mods_citations_for(deepbills_bill_version_id_parts):
	metadata = mods_metadata_for(deepbills_bill_version_id_parts)

	return metadata["citations"]

### DeepBills ###

# XXX: Modified from deepbills_url_for() in unitedstates/congress/tasks/deepbills.py
def deepbills_url_for(deepbills_bill_version_id_parts):
  return "http://deepbills.cato.org/api/1/bill?congress=%s&billtype=%s&billnumber=%s&billversion=%s" % ( deepbills_bill_version_id_parts["congress"], deepbills_bill_version_id_parts["billtype"], deepbills_bill_version_id_parts["billnumber"], deepbills_bill_version_id_parts["billversion"] )

# XXX: Modified from fetch_single_bill_json() in unitedstates/congress/tasks/deepbills.py
def fetch_deepbills_bill_json(deepbills_bill_version_id_parts):
  return json.loads(urllib.urlopen(deepbills_url_for(deepbills_bill_version_id_parts)).read())

# XXX: Borrowed from unitedstates/congress/tasks/deepbills.py
def extract_catoxml_bill_body_from(single_bill_json):
  return single_bill_json["billbody"].encode("utf-8")

def fetch_deepbills_bill_xml(deepbills_bill_version_id_parts):
	# TODO: This should check for the file on the local server first.
	if False:
		return ""
	else:
		return extract_catoxml_bill_body_from(fetch_deepbills_bill_json(deepbills_bill_version_id_parts))

def is_special_segment(entity_value_segment):
	return (entity_value_segment in [ "note", "etseq" ])

def add_special_segment(citation, entity_value_segment):
	if "special" not in citation:
		citation["special"] = entity_value_segment
	else:
		raise ValueError("Special segment already defined in citation")

	return citation

def parse_prefixed_segments(citation, entity_value_segments):
	prefix_map = {
		"d": "division",
		"t": "title",
		"st": "subtitle",
		"pt": "part",
		"spt": "subpart",
		"ch": "chapter",
		"sch": "subchapter",
		"s": "section",
		"ss": "subsection",
		"p": "paragraph",
		"sp": "subparagraph",
		"cl": "clause",
		"scl": "subclause",
		"i": "item",
		"si": "subitem",
	}

	for entity_value_segment in entity_value_segments:
		try:
			prefix, segment = entity_value_segment.split(":")

			if prefix_map[prefix] not in citation:
				citation[prefix_map[prefix]] = segment
			else:
				raise ValueError("Segment already defined in citation: %s" % ( prefix_map[prefix] ))
		except ValueError:
			if is_special_segment(entity_value_segment):
				add_special_segment(citation, entity_value_segment)
			else:
				if "extra" not in citation:
					citation["extra"] = []

				citation["extra"].append(entity_value_segment)

	return citation

def build_citation(entity_value_segments, entity_value_segment_names):
	citation = {}

	i = 0
	while len(entity_value_segments) > 0:
		entity_value_segment = entity_value_segments.pop(0)

		if is_special_segment(entity_value_segment):
			add_special_segment(citation, entity_value_segment)
		else:
			try:
				citation[entity_value_segment_names[i]] = entity_value_segment
			except IndexError:
				break

		i += 1

	citation = parse_prefixed_segments(citation, entity_value_segments)

	return citation

def segment_names_for(entity_type):
	segment_name_map = {
		"uscode": {
			"usc": [ "subtype", "title", "section", "subsection", "paragraph", "subparagraph", "clause", "subclause", "item", "subitem" ],
			"usc-chapter": [ "subtype", "title", "chapter", "subchapter" ],
			"usc-appendix": [ "subtype", "title", "section" ],
		},
		"act": [ "act" ],
		"statute-at-large": [ "type", "volume", "page" ],
		"public-law": [ "type", "congress", "law" ],
	}

	if entity_type in segment_name_map:
		return segment_name_map[entity_type]

	return []

def entity_value_segments_from(entity_value):
	return entity_value.split("/")

def deepbills_citation_for(entity_type, entity_value, entity_ref_text, entity_proposed=False):
	entity_value_segment_names = segment_names_for(entity_type)
	entity_value_segments = entity_value_segments_from(entity_value)

	if entity_type in [ "uscode" ]:
		entity_subtype = entity_value_segments[0]

		citation = build_citation(entity_value_segments, entity_value_segment_names[entity_subtype])
	else:
		citation = build_citation(entity_value_segments, entity_value_segment_names)

	citation["type"] = entity_type
	citation["value"] = entity_value
	citation["proposed"] = True if entity_proposed else False

	import re
	citation["text"] = re.sub(r"(\s+)", " ", entity_ref_text)

	return citation

def govtrack_collapsed_paragraph_for(deepbills_citation, start_after="section"):
	type = deepbills_citation["type"]

	segment_names = segment_names_for(type)

	if type in [ "uscode" ]:
		segment_names = segment_names[deepbills_citation["subtype"]]

	try:
		i = segment_names.index(start_after)
	except ValueError:
		i = -1

	if segment_names == []:
		segment_names = [ "division", "title", "subtitle", "part", "subpart", "chapter", "subchapter", "section", "subsection", "paragraph", "subparagraph", "clause", "subclause", "item", "subitem" ]

	segment_names = segment_names[i+1:]

	collapsed_paragraph = ""
	for segment_name in segment_names:
		if ( segment_name in deepbills_citation ) and ( deepbills_citation[segment_name] ):
			collapsed_paragraph += "(" + deepbills_citation[segment_name] + ")"

	if "special" in deepbills_citation:
		if collapsed_paragraph != "":
			collapsed_paragraph += " "

		if deepbills_citation["special"] == "etseq":
			collapsed_paragraph += "et seq."
		else:
			collapsed_paragraph += deepbills_citation["special"]

	return ( collapsed_paragraph if collapsed_paragraph != "" else None )

def govtrack_citation_text_for(deepbills_citation):
	govtrack_citation_text = ""
	collapsed_paragraph = govtrack_collapsed_paragraph_for(deepbills_citation)

	if deepbills_citation["type"] == "uscode":
		govtrack_citation_text += deepbills_citation["title"]
		govtrack_citation_text += " U.S.C."

		if deepbills_citation["subtype"] == "usc-appendix":
			govtrack_citation_text += " App."

		if deepbills_citation["subtype"] == "usc-chapter":
			govtrack_citation_text += " Chapter "
			govtrack_citation_text += deepbills_citation["chapter"]

			collapsed_paragraph = None
		else:
			if "section" in deepbills_citation:
				govtrack_citation_text += " "
				govtrack_citation_text += deepbills_citation["section"]

		if collapsed_paragraph is not None:
			govtrack_citation_text += collapsed_paragraph
	elif deepbills_citation["type"] == "act":
		collapsed_paragraph = govtrack_collapsed_paragraph_for(deepbills_citation, "act")

		if collapsed_paragraph is not None:
			govtrack_citation_text += collapsed_paragraph
			govtrack_citation_text += " of "

		govtrack_citation_text += deepbills_citation["act"]
	elif deepbills_citation["type"] == "statute-at-large":
		govtrack_citation_text += deepbills_citation["volume"]
		govtrack_citation_text += " U.S.C."
		govtrack_citation_text += deepbills_citation["page"]
	elif deepbills_citation["type"] == "public-law":
		# XXX: We might want to add segment citations here.
		govtrack_citation_text += "Public Law " # XXX: CatoXML says the citation is normally "P.L."
		govtrack_citation_text += deepbills_citation["congress"]
		govtrack_citation_text += "-"
		govtrack_citation_text += deepbills_citation["law"]

	return govtrack_citation_text

def govtrack_citation_for(entity_type, entity_value, entity_ref_text, entity_proposed=False):
	deepbills_citation = deepbills_citation_for(entity_type, entity_value, entity_ref_text, entity_proposed)

	govtrack_citation = {}

	govtrack_citation["text"] = govtrack_citation_text_for(deepbills_citation)

	if deepbills_citation["type"] == "uscode":
		if deepbills_citation["subtype"] == "usc":
			govtrack_citation["type"] = "usc-section"
		else:
			govtrack_citation["type"] = deepbills_citation["subtype"]

		govtrack_citation["title"] = deepbills_citation["title"]

		if deepbills_citation["subtype"] == "usc-appendix":
			govtrack_citation["title"] += "a"

		if deepbills_citation["subtype"] == "usc-chapter":
			govtrack_citation["chapter"] = deepbills_citation["chapter"]
			govtrack_citation["key"] = "usc/chapter/" + govtrack_citation["title"] + "/" + govtrack_citation["chapter"]
		else:
			if "section" in deepbills_citation:
				# XXX: This is a quick-and-dirty range finder.
				if ".." in deepbills_citation["section"]:
					govtrack_citation["type"] = "usc"
					govtrack_citation["section"], govtrack_citation["range_to_section"] = deepbills_citation["section"].split("..")
					govtrack_citation["paragraph"] = None
				else:
					govtrack_citation["section"] = deepbills_citation["section"]
					govtrack_citation["paragraph"] = govtrack_collapsed_paragraph_for(deepbills_citation)
			else:
				govtrack_citation["section"] = None

			if not govtrack_citation["section"]:
				govtrack_citation["key"] = "usc/title/" + govtrack_citation["title"]
			else:
				govtrack_citation["key"] = "usc/" + govtrack_citation["title"] + "/" + govtrack_citation["section"]
	elif deepbills_citation["type"] == "statute-at-large":
		govtrack_citation["type"] = "statutes_at_large"
	elif deepbills_citation["type"] == "public-law":
		govtrack_citation["type"] = "slip_law"
		govtrack_citation["congress"] = int(deepbills_citation["congress"])
		govtrack_citation["number"] = int(deepbills_citation["law"])
	else:
		govtrack_citation["type"] = "unknown" # deepbills_citation["type"]

	return govtrack_citation

def deepbills_citations_for(deepbills_bill_version_id_parts):
	from lxml import etree

	citations = {}

	deepbills_bill = etree.fromstring(fetch_deepbills_bill_xml(deepbills_bill_version_id_parts))
	ns = { "cato": "http://namespaces.cato.org/catoxml" }

	entity_refs = deepbills_bill.findall(".//cato:entity-ref", namespaces=ns)

	for entity_ref in entity_refs:
		entity_type = entity_ref.get("entity-type")
		entity_value = entity_ref.get("value")
		entity_proposed = True if ( entity_ref.get("value", "false") == "true" ) else False

		if entity_value is not None:
			citation = govtrack_citation_for(entity_type, entity_value, entity_ref.text, entity_proposed)

			if entity_type not in citations:
				citations[entity_type] = []

			citations[entity_type].append(citation)

	return citations


##############################################################################


deepbills_bill_index = fetch_deepbills_bill_index()

for deepbills_bill_version_id_parts in deepbills_bill_index:
	# XXX
	if deepbills_bill_version_id_parts["billtype"] != "hr":
		continue

	mods_citations = mods_citations_for(deepbills_bill_version_id_parts)

	try:
		deepbills_citations = deepbills_citations_for(deepbills_bill_version_id_parts)
	except IOError:
		print "Timeout:", deepbills_url_for(deepbills_bill_version_id_parts)
		continue

	if ( mods_citations is not None ) or ( deepbills_citations is not None ):
		print deepbills_bill_version_id_parts
#		print mods_citations
#		print deepbills_citations

		mods_citation_set = set()
		deepbills_citation_set = set()

		for mods_citation in mods_citations:
			if "key" in mods_citation:
				mods_citation_set.add(mods_citation["key"])
			else:
				mods_citation_set.add(mods_citation["text"])

		for deepbills_type in deepbills_citations:
			for deepbills_citation in deepbills_citations[deepbills_type]:
				if "key" in deepbills_citation:
					deepbills_citation_set.add(deepbills_citation["key"])
				else:
					deepbills_citation_set.add(deepbills_citation["text"])

		for mods_citation_key in mods_citation_set:
			if mods_citation_key not in deepbills_citation_set:
				print "'%s' not in DeepBills citations" % ( mods_citation_key )

		for deepbills_citation_key in deepbills_citation_set:
			if deepbills_citation_key not in mods_citation_set:
				print "'%s' not in MODS citations" % ( deepbills_citation_key )

		print ""

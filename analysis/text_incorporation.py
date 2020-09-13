#!script
#;encoding=utf-8

# See if the text of one bill occurs within the text of another.
# This works in two stages. In the "analysis" stage, all enacted
# bills are compared to likely candidates for incorporated bills
# and comparison output is saved to a CSV file. Only comparisons
# not yet performed are run, and the CSV file is incremented with
# new data. In the "load" step, the CSV data is loaded into the
# database and old data in the database is cleared, with some
# filtering - only pairs of bills that actually represent textual
# incorporation are put into the database.
#
# To re-run, run in bash:
#
# for congress in {109..115}; do
#  echo $congress;
#  analysis/text_incorporation.py analyze $congress;
#  analysis/text_incorporation.py load $congress;
# done

import sys
import re
import unicodedata
from io import StringIO
import lxml.etree
from numpy import percentile

if sys.stdout.isatty():
  from tqdm import tqdm
else:
  def tqdm(iter, *args, **kwargs):
    return iter

def extract_text(fn):
  # Given a path to a bill text XML file from Congress,
  # serialize the substantive legislative text into a
  # flat string that can be passed to text comparison
  # tools. Returns the string.

  # Parse the XML and move to the <legis-body> node.
  try:
    dom = lxml.etree.parse(fn)
  except lxml.etree.XMLSyntaxError:
    raise ValueError("xml syntax error")
  if (dom.find("legis-body") or dom.find("resolution-body")) is None:
    raise ValueError("missing legis-body or resolution-body in " + fn)

  # Serializes the content of a node into plain text.
  def serialize_within_node(node, buf):
    # Skip struck-out text.
    if node.get("changed") == "deleted":
      return

    # Skip headings and enums (numbering) entirely,
    # as these may not be the same if the text is moved
    # into another bill. But still write out the text that
    # occurs after this node's close tag.
    if node.tag in ("header", "enum"):
      return

    # Skip some entire sections that are not typically preserved
    # verbatim when provisions are incorporated into other
    # legislative vehicles. See if this node contains a <header>
    # node whose text is "short title", etc. and then skip the
    # whole section.
    h = node.find("header")
    if h is not None and h.text is not None and h.text.lower().strip() in \
      ("short title", "effective date"):
      return

    # Write the text that occurs before the first child.
    if node.text:
      buf.write(node.text)

    # ... and then the children ...
    for child in node:
      serialize_node(child, buf)

    # ... and then implied whitespace on block-level elements so
    # that the text does not run together with subsequent block-level
    # content...
    if node.tag in ("text",):
      buf.write(" ")

  # Serializes a node into plain text.
  def serialize_node(node, buf):
    # Serialize the content of this node.
    serialize_within_node(node, buf)

    # And then the text that occurs after the closing tag
    # of the element and before the next element.
    if node.tail:
      buf.write(node.tail)

  # Serialize the bill text XML document. Serialie each legis-body
  # or resolution-body. There may be more than one such node if the
  # bill is in amendment form.
  buf = StringIO()
  for n in dom.xpath("legis-body|resolution-body"):
    serialize_node(n, buf)
  text = buf.getvalue()

  # Normalize the text to make comparisons less picky.

  # Make comparison case-insensitive.
  text = text.lower()

  # Normalize whitespace, dashes, and punctuation.
  text = re.sub("\\s+", " ", text) # collapse whitespace into single spaces
  text = re.sub("[−–—~‐]+", "-", text) # lots of dash types
  text = re.sub("\\W+ ", " ", text) # remove punctuation preceding whitespace

  # Replace common phrases with single, atomic words so that they count
  # for less in the analysis phase of this script.
  text = re.sub("is amended by striking", "/IABS/", text)
  text = re.sub("is amended by adding at the end the following", "/IABAATETF/", text)
  text = re.sub("after the date of enactment of this act", "/ATDOEOTA/", text)

  # Make comparison insensitive to Unicode details that can be removed,
  # like accent marks. I have no reason to believe this matters, but
  # the more unicode that can be removed, the better, I guess. This
  # decomposes Unicode characters and then removes combining characters.
  text = "".join(c for c in unicodedata.normalize('NFKD', text)
    if not unicodedata.combining(c))

  return text

def to_words(text, word_map):
  # Splice on whitespace and convert the words to a unicode string where code points map to words in the original.
  return "".join([word_map.setdefault(w, chr(len(word_map)+32)) for w in text.split(" ")])

def from_words(wordlist, word_map):
  # Turn the Unicode string where code points map to words back to the original string.
  return " ".join(word_map[c] for c in wordlist)

def prepare_text1(text1):
  # Load the text into a difflib.SequenceMatcher. Convert the text to "words"
  # first, so that the unit of comparison is words. The docs say loading it
  # into seq2 is faster for iterating over documents (as seq1).
  from difflib import SequenceMatcher
  word_map = { } # for to_words
  text1w = to_words(text1, word_map)
  sm = SequenceMatcher()
  sm.set_seq2(text1w)
  return (sm, word_map, len(text1w))

def compare_text(text2, sm, word_map, text1w_len):
  # Clone so that the orginal can be reused on the next call.
  word_map = dict(word_map)

  # Update the SequenceMatcher, which according to the docs is
  # faster if we keep the instance and update seq1 on each call
  # with the new text.
  text2w = to_words(text2, word_map)
  sm.set_seq1(text2w)

  # Invert the word_map for from_words.
  word_map = { v: k for k, v in word_map.items() }

  # Perform diff, getting the "matching blocks" of text. These
  # blocks may be single words or the entire text2 document,
  # distributed anywhere in the text1 document.
  blocks = sm.get_matching_blocks()[0:-1] # the last block is empty
  blocks = [{
    "text1_start": m.b,
    "text2_start": m.a,
    "size": m.size,
  } for m in blocks]

  # Annotate each block with its distance to preceding and surrounding
  # blocks.
  for i in range(1, len(blocks)):
    blocks[i]['text1_nbefore'] = blocks[i]['text1_start'] - (blocks[i-1]['text1_start']+blocks[i-1]['size'])
    blocks[i]['text2_nbefore'] = blocks[i]['text2_start'] - (blocks[i-1]['text2_start']+blocks[i-1]['size'])
    blocks[i-1]['text1_nafter'] = blocks[i]['text1_nbefore']
    blocks[i-1]['text2_nafter'] = blocks[i]['text2_nbefore']

  # We want to compute a number that indicates how much of text2
  # appears in text1. So we compute the number of words in text2
  # that appear in text1 and divide by the total number of words
  # in text2. Drop blocks that are so far away from surrounding
  # text that they probably don't represent a contiguous part of
  # copied text between the documents.
  matched_blocks = [
    b
    for b in blocks
    if b['size'] > 10 or (b['size'] > b.get("text1_nbefore", 0) and b['size'] > b.get("text1_nafter", 0) and b['size'] > b.get("text2_nbefore", 0) and b['size'] > b.get("text2_nafter", 0))
    ]
  extract = "...".join(from_words(text2w[block['text2_start']:block['text2_start']+block['size']], word_map) for block in matched_blocks)
  ratio1 = sum(b['size'] for b in matched_blocks) / float(text1w_len)
  ratio2 = sum(b['size'] for b in matched_blocks) / float(len(text2w))
  return ratio1, ratio2, extract

def is_text_incorporated(b1_ratio, b2_ratio, cmp_text_len):
  # The bills are substantially and symmetrically similar to each other
  # and the text in common is large enough to exclude cases where all of
  # the substance in the bills are in the dis-similar parts. The smaller
  # the absolute amount in common, the higher the relative threshold.
  if b1_ratio*b2_ratio > max(.95-0.0006*(cmp_text_len-300), .66) and cmp_text_len > 300:
    return True

  # One bill is substantially (>33%) incorporated within the other
  # and the text in common is significantly large to ensure that
  # there are substantive provisions in that part. Require a higher
  # percentage of overlap in shorter bills.
  if max(b1_ratio, b2_ratio) > max(.8-0.00015*(cmp_text_len-800), .33) and cmp_text_len > 800:
    return True

  # One bill has provisions incorporated within the other, and though
  # it's a small part of the bill, it's a large bill and the text
  # in common is quite large.
  if (b1_ratio>.15 or b2_ratio>.15) and cmp_text_len > 8000:
    return True

  return False

def compare_bills(b1, b2):
  from bill.billtext import get_bill_text_metadata
  fn1 = get_bill_text_metadata(b1, None)['xml_file']
  fn2 = get_bill_text_metadata(b2, None)['xml_file']
  text1 = extract_text(fn1)
  state = prepare_text1(text1)
  print(b1.id, str(b1))
  print(b2.id, str(b2))
  ratio1, ratio2, text = compare_text(extract_text(fn2), *state)
  print(ratio1, ratio2, len(text))
  print(text)
  print(is_text_incorporated(ratio1, ratio2, len(text)))
  print()


if __name__ == "__main__" and sys.argv[1] == "analyze":
  # Look at all enacted bills find bills that are substantially
  # similar or have text incorporated into it.
  #
  # Write out a CSV table.
  
  import itertools, csv, os.path, shutil
  from bill.models import *
  from bill.billtext import get_bill_text_metadata

  from django.utils import timezone

  congress = int(sys.argv[2])

  all_bills = Bill.objects.filter(
    congress=congress,
    bill_type__in=(BillType.house_bill, BillType.senate_bill, BillType.house_joint_resolution, BillType.senate_joint_resolution))
  enacted_bills = list(all_bills.filter(
    current_status__in=BillStatus.final_status_enacted_bill))

  # Write to CSV, to a temporary file for now.
  with open("/tmp/text_comparison.csv", "w") as outfile:
    writer = csv.writer(outfile)

    # Load the current comparison data so we know what bill texts
    # we've already compared and copy those comparisons into the
    # output.
    csv_fn = "data/analysis/by-congress/%d/text_comparison.csv" % congress
    existing_comps = set()
    if os.path.exists(csv_fn):
      for row in csv.reader(open(csv_fn)):
        timestamp, b1_id, b1_versioncode, b1_ratio, b2_id, b2_versioncode, b2_ratio, cmp_text_len, cmp_text \
           = row
        existing_comps.add( ((b1_id, b1_versioncode), (b2_id, b2_versioncode) ) )
        writer.writerow(row)

    # For each enacted bill..
    for b1 in tqdm(enacted_bills):
      # Load the enacted bill's text.

      # Loads current metadata and text for the bill.
      try:
        md1 = get_bill_text_metadata(b1, None)
        text1 = extract_text(md1['xml_file'])
      except TypeError: # no bill text at all (accessing [...] of None)
        continue
      except KeyError: # no xml_file
        continue
      except ValueError: # xml is bad
        continue

      state = prepare_text1(text1)

      # Use Solr's More Like This query to get a preliminary list of
      # bills textually similar to each enacted bill, which lets us
      # cut down on the number of comparisons that we need to run
      # by a factor of around 100. Pull between 10 and 50 similar
      # bills -- depending on how large of a bill the enacted bill
      # is. An authorization bill can have lots of bills incorporated
      # into it, but a short bill could not have very many.

      from haystack.query import SearchQuerySet
      qs = SearchQuerySet().using("bill").filter(indexed_model_name__in=["Bill"])\
        .filter(congress=b1.congress).more_like_this(b1)
      how_many = min(50, max(10, len(text1)/1000))
      similar_bills = set(r.object for r in qs[0:how_many])

      # Add in any related bills identified by CRS. Related bills aren't
      # exhaustive, which is why we also look at textually similar bills,
      # but on very large bills (like big approps bills) textual similarity
      # doesn't exhaustively include everythig either in the top ~50 results.
      similar_bills |= set(rb.related_bill for rb in RelatedBill.objects.filter(bill=b1))
      
      # Iterate over each similar bill.

      for b2 in sorted(similar_bills, key = lambda x : (x.congress, x.bill_type, x.number)):
        # Don't compare to other enacted bills.
        if b2.current_status in BillStatus.final_status_enacted_bill:
          continue

        # Don't compare bills to resolutions.
        if b1.noun != b2.noun:
          continue

        # Get the second bill's most recent text document's metadata.
        md2 = get_bill_text_metadata(b2, None)
        if not md2: # text may not be available yet
          continue

        # Did we do a comparison already? Skip if so.
        key = ((b1.congressproject_id, md1['version_code']), (b2.congressproject_id, md2['version_code']))
        if key in existing_comps:
          continue

        # The enacted bill must be newer than the non-enacted bill.
        # Since authorizations are repeated from year to year, we
        # should exclude cases where a bill looks like one previously
        # enacted. Since text is not always published simultaneously
        # with status, especially often for enrolled bills, we can
        # look at the text date but better the bill's current status.
        # Sometimes the text gets ahead of the bill, like when a bill
        # gets reprinted when it moves across chambers, which doesnt
        # represent substantive action. hr1567-114 had a text print
        # after its companion bill s1252-114 was enrolled.
        if b1.current_status_date <= b2.current_status_date:
          continue

        # Load the second bill's text.
        try:
          text2 = extract_text(md2['xml_file'])
        except KeyError: # no xml_file
          continue
        except ValueError: # xml is bad
          continue

        # Run comparison.
        ratio1, ratio2, text = compare_text(text2, *state)

        # Write out the comparison. We write out everything so that we know
        # we've done the computation and don't need to do it again later.
        writer.writerow([
          timezone.now().isoformat(),

          b1.congressproject_id, md1['version_code'],
          ratio1,

          b2.congressproject_id, md2['version_code'],
          ratio2,

          len(text),
          text[:1000].encode("utf8") if ((ratio1 > .1 or ratio2 > .1) and len(text) > 500) else "",
          ])

  shutil.move("/tmp/text_comparison.csv", csv_fn)

elif __name__ == "__main__" and sys.argv[1] == "load":
  # Update the Bill.text_incorporation field in our database.
  # Since a bill can be incorporated into many enacted bills,
  # we have to scan the complete table to collect all of the
  # records in which a bill is mentioned.

  import csv, collections
  from bill.models import Bill

  congress = int(sys.argv[2])

  csv_fn = "data/analysis/by-congress/%d/text_comparison.csv" % congress

  # Identify the most recent bill version for each bill. Since the
  # CSV file is in chronological order by the date the text analysis
  # was performed, and each line uses only the most recent text for
  # a bill, we can look at the last occurrence of a bill to see what
  # text version is the latest. On a second pass, we'll skip analyses
  # over earlier versions of a bill.
  latest_version_code = { }
  for row in csv.reader(open(csv_fn)):
    timestamp, b1_id, b1_versioncode, b1_ratio, b2_id, b2_versioncode, b2_ratio, cmp_text_len, cmp_text \
       = row
    latest_version_code[b1_id] = b1_versioncode
    latest_version_code[b2_id] = b2_versioncode

  # Collate the text incorporation data by bill.
  text_incorporation = collections.defaultdict(lambda : { })
  for row in csv.reader(open(csv_fn)):
    timestamp, b1_id, b1_versioncode, b1_ratio, b2_id, b2_versioncode, b2_ratio, cmp_text_len, cmp_text \
       = row
    cmp_text_len = int(cmp_text_len)

    # b1 is the enacted bill.
    # b2 is a non-enacted bill that might have had text incorporated into b1.

    # Skip if this record is for an outdated version of either bill.
    if b1_versioncode != latest_version_code[b1_id]: continue
    if b2_versioncode != latest_version_code[b2_id]: continue

    # Does this record represent enough text similarity that it is worth
    # loading into the database? We'll treat this record as indicating
    # similarity if...

    # For exceedingly formulaic bills, we'll only identify identical bills.
    # Bills naming buildings etc. are formulaic and produce text similarity
    # to other bills of the same type, because the part that differs is very
    # small. So we use a very high threshold for comparison. This may not
    # be needed. I added it after seeing the analysis produce false positives,
    # but then I discovered that cmp_text_len was not being compared right in
    # the next block so this may actually not be needed to help.
    b1_ratio = round(float(b1_ratio),3)
    b2_ratio = round(float(b2_ratio),3)
    b1 = Bill.from_congressproject_id(b1_id)
    if  b1.title_no_number.startswith("A bill to designate ") \
     or b1.title_no_number.startswith("To designate ") \
     or b1.title_no_number.startswith("To name ") \
     or b1.title_no_number.startswith("A bill for the relief of ") \
     or "Commemorative Coin Act" in b1.title_no_number:
      if b1_ratio*b2_ratio < .85:
        continue

    # For other bills...
    if is_text_incorporated(b1_ratio, b2_ratio, cmp_text_len):
      # Index this information with both bills.

      # For b2, we're saying that it (or parts of it) were enacted
      # through these other bills...
      text_incorporation[b2_id][b1_id] = {
        "my_version": b2_versioncode,
        "my_ratio": b2_ratio,
        "other": b1_id,
        "other_version": b1_versioncode,
        "other_ratio": b1_ratio,
        #"text": cmp_text, # Unicode isnt being saved into the db properly which causes
                           # equality comparisons to fail when checking if records need
                           # updating, and we're not using this anyway, so don't include it.
      }

      # For b1, which was enacted, we're saying that the bill's
      # legislative history starts with these other bills.
      text_incorporation[b1_id][b2_id] = {
        "my_version": b1_versioncode,
        "my_ratio": b1_ratio,
        "other": b2_id,
        "other_version": b2_versioncode,
        "other_ratio": b2_ratio,
        #"text": cmp_text, # see above
      }

  # Reformat so each bill has a stable-ordered list of other bills rather than
  # an unordered mapping.
  for b in text_incorporation:
    text_incorporation[b] = sorted(text_incorporation[b].values(), key=lambda item : (
      -item['my_ratio'], item['other_ratio'], item['my_version'], item['other'], item['other_version']))

  # Get the haystack index.
  from bill.search_indexes import BillIndex
  bill_index = BillIndex()

  # Helper to update a bill.
  def save_bill(b):
    # Save the field we care about.
    b.save(update_fields=['text_incorporation'])

    # Re-index in haystack.
    b.update_index(bill_index)

    # Ensure events are up to date.
    #b.create_events() # add once this info affects events

  # Update bills.
  seen_bills = set()
  for b_id, info in tqdm(sorted(text_incorporation.items()), desc="Updating"):
    b = Bill.from_congressproject_id(b_id)
    if b.text_incorporation != info:
      # Updated!
      b.text_incorporation = info
      save_bill(b)
    seen_bills.add(b.id)

  # Clear out all bills from this Congress that should have
  # no text incorporation data but do have something that's
  # no longer valid.
  for b in tqdm(list(Bill.objects
    .filter(congress=congress)
    .exclude(text_incorporation=None)
    .exclude(id__in=seen_bills)), desc="Clearing"):
    b.text_incorporation = None
    save_bill(b)

elif __name__ == "__main__" and sys.argv[-1] == "test":
  # Look at our table and see how many relationships it identified
  # that are not already known to be identical bills.
  import csv
  from bill.models import Bill, RelatedBill
  congress = 114
  csv_fn = "data/analysis/by-congress/%d/text_comparison.csv" % congress
  for row in csv.reader(open(csv_fn)):
    timestamp, b1_id, b1_versioncode, b1_ratio, b2_id, b2_versioncode, b2_ratio, cmp_text_len, cmp_text = row
    b1_ratio = float(b1_ratio)
    b2_ratio = float(b2_ratio)
    cmp_text_len = int(cmp_text_len)
    if   (b1_ratio*b2_ratio > .95 and cmp_text_len > 400) \
      or (b1_ratio*b2_ratio > .66 and cmp_text_len > 1500) \
      or ((b1_ratio>.30 or b2_ratio>.30) and cmp_text_len > 7500) \
      or ((b1_ratio>.15 or b2_ratio>.15) and cmp_text_len > 15000):
      b1 = Bill.from_congressproject_id(b1_id)
      b2 = Bill.from_congressproject_id(b2_id)
      r = RelatedBill.objects.filter(bill=b1, related_bill=b2, relation="identical")
      #if r.count() == 0:
      print(b1_id, b2_id, r)
      print(b1)
      print(b2)
      print()

elif __name__ == "__main__" and sys.argv[1] == "graph":
  # Make a graph of text incorporation relationships.
  # requires: sudo apt-get install graphviz && pip install graphviz
  from bill.models import Bill
  from graphviz import Digraph

  # extract a subset of the data - paint the graph to determine
  # connectivity
  paint = { }
  for bill in tqdm(Bill.objects.filter(congress=114).exclude(text_incorporation=None), desc="Connectivity"):
    for rec in bill.text_incorporation:
      b1_id = bill.congressproject_id
      b2_id = rec["other"]
      if b1_id not in paint and b2_id not in paint:
        paint[b1_id] = len(paint)
        paint[b2_id] = paint[b1_id]
      elif b1_id in paint and b2_id not in paint:
        paint[b2_id] = paint[b1_id]
      elif b1_id not in paint and b2_id in paint:
        paint[b1_id] = paint[b2_id]
      else:
        # merge graph
        b2_color = paint[b2_id]
        for k in paint:
          if paint[k] == b2_color:
            paint[k] = paint[b1_id]

  # Which color has the most nodes?
  #max_connectivity = max(paint, key = lambda bill_id : len([b for b, p in paint.items() if p == paint[bill_id]]) )

  def add_newlines(text):
    chars_per_line = 16
    nchars_per_line = int(len(text) / max(1, round(len(text) / chars_per_line)))
    words = []
    charcount = 0
    for w in text.split(" "):
      if charcount+len(w) > nchars_per_line:
        if len(" ".join(words)) > 90:
          words.append("...")
          break
        words.append("\\n")
        charcount = 0
      words.append(w)
      charcount += len(w)
    return " ".join(words)
  
  g = Digraph(name="Text Incorporation",
    graph_attr={
      "mindist": "0",
      "overlap": "false",
      "splines": "true",
      "root": sys.argv[2] })

  for bill in tqdm(Bill.objects.filter(congress=114).exclude(text_incorporation=None), desc="Graph"):
    # Draw a subgraph.
    if paint[bill.congressproject_id] != paint[sys.argv[2]]:
      continue
      # "s1808-114", "hr34-114"

    g.node(
      bill.congressproject_id,
      label=add_newlines(bill.title),
      #tooltip=bill.display_number_no_congress_number,
      color="red" if bill.is_success() else "black" #("green" if bill.was_enacted_ex() else "black")
      )

    for rec in bill.text_incorporation:
      # Since the data is symmetric, only draw an edge going one way.
      # Each edge is between a non-enacted bill and an enacted bill,
      # so draw the edges in that direction.
      b2 = Bill.from_congressproject_id(rec["other"])
      if bill.is_success() and not b2.is_success():
        continue
      elif not bill.is_success() and b2.is_success():
        pass
      else:
        raise ValueError()

      g.edge(
          bill.congressproject_id,
          rec["other"],
          label="%d%%" % int(round(rec["my_ratio"]*100)),
          )
  
  g.engine = 'twopi'
  svg = g.pipe(format='svg')
  print(svg)

elif __name__ == "__main__" and sys.argv[1] == "extract-text":
  print(extract_text(sys.argv[2]).encode("utf8"))


elif __name__ == "__main__" and len(sys.argv) == 3:
  # Compare two bills.
  from bill.models import *
  b1 = Bill.from_congressproject_id(sys.argv[1])
  b2 = Bill.from_congressproject_id(sys.argv[2])
  compare_bills(b1, b2)

elif __name__ == "__main__":
  # Look at all enacted bills that had a companion.

  from django.db.models import F
  from bill.models import *
  # Since identical is symmetric, only take one pair.
  for br in RelatedBill.objects\
    .filter(relation="identical", related_bill__id__gt=F('bill__id'))\
    .filter(bill__congress=114, bill__current_status=BillStatus.enacted_signed):
    if len(sys.argv) > 1:
      if sys.argv[1] not in str(br.bill):
        continue

    compare_bills(br.bill, br.related_bill)

elif __name__ == "__main__":
  # Compare XML files given as arguments.
  import sys
  text1 = extract_text(sys.argv[1])
  state = prepare_text1(text1)
  for fn in sys.argv[2:]:
    text2 = extract_text(fn)
    ratio, text = compare_text(text2, *state)
    if len(text) > 150/(ratio**6) and ratio > .66:
      print(fn)
      print(ratio, text)

# compare being dumb to using CRS identical bills to using text incorporation
#  from bill.models import Bill, RelatedBill, BillStatus
#
#  bills = Bill.objects.filter(congress=114)
#
#  len([b for b in bills if b.noun == "bill"])
#  # 10074
#
#  def ok1(b): return b and b.current_status in BillStatus.final_status_enacted_bill
#  len([b for b in bills if b.noun == "bill" and ok1(b)])
#  # 325
#
#  def ok2(b): return ok1(b) or ok1(Bill.objects.filter(relatedtobills__bill=b, relatedtobills__relation="identical").first())
#  len([b for b in bills if b.noun == "bill" and ok2(b)])
#  # 416
#
#  def ok3(b): return b.was_enacted_ex()
#  len([b for b in bills if b.noun == "bill" and ok3(b)])
#  # 692


#!script

from bill.models import *
from registration.helpers import json_response

from common.decorators import render_to
from twostream.decorators import anonymous_view

import random, codecs

@anonymous_view
@render_to('bill/bill_or_not.html')
def bill_or_not(request):
	return { }

pregen_bill_titles = None
def make_random_bill_title(bill_type):
	# load pregenerated bill titles
	global pregen_bill_titles
	if pregen_bill_titles == None:
		pregen_bill_titles = { "bill": [], "resolution": [] }
		for bill_type, lst in pregen_bill_titles.items():
			with codecs.open("data/misc/april_fools_bill_titles_%s.txt" % bill_type, "r", "utf-8") as f:
				for line in f:
					lst.append(line.strip())

	return random.choice(pregen_bill_titles[bill_type])

@json_response
def load_game(request):
	type_map = { "bill": (BillType.house_bill, BillType.senate_bill),
		"resolution": (BillType.house_resolution, BillType.senate_resolution) }
	
	bill_type = random.choice(["bill", "bill", "resolution"]) # don't do resolutions so much
	qs = Bill.objects.filter(bill_type__in=type_map[bill_type], congress__gt=109)
	actual_bill = qs[random.randint(0, qs.count()-1)]

	return {
		"bill_type": bill_type,
		"bill_number": actual_bill.display_number_no_congress_number,
		"actual_bill_title": actual_bill.title_no_number,
		"actual_bill_link": actual_bill.get_absolute_url(),
		"actual_bill_intro_date": actual_bill.introduced_date.strftime("%b %d, %Y"),
		"fake_bill_title": make_random_bill_title(bill_type),
	}

if __name__ == "__main__":
	
	# Pre-generate 10,000 random bill titles.

	from nltk.model.ngram import NgramModel
	
	import re
	
	corpus = { "bill": [], "resolution": [] }
	for b in Bill.objects.filter(congress__gte=109):
		title = b.title_no_number + " ###"
		if title.startswith("To "): continue
		title = re.sub(r" \d\d\d\d", " 2015", title)
		title = re.sub(r"\.$", "", title)
		corpus[b.noun].append( title.split(" ") )
		
	# Generate a few separate models.
	models = {
		("bill", 2): NgramModel(2, corpus["bill"]),
		("bill", 3): NgramModel(3, corpus["bill"]),
		("resolution", 2): NgramModel(2, corpus["resolution"]),
		("resolution", 3): NgramModel(3, corpus["resolution"]),
	}
	
	def make_random_bill_title(bill_type):
		# Generate a sentence, one word at a time.
		sentence = []
		while True:
			model = models[(bill_type, 2 if (len(sentence) % 2) == 0 else 3)]
			wd = model.choose_random_word(sentence)
			
			if wd == "###":
				if len(sentence) > 6:
					# finished
					break
				else:
					# sentence was too short, try again from scratch
					sentence = []
					continue
					
			sentence.append(wd)
			
			# Are we *too* probable? I don't want to generate actual bill titles!
			# If so, start over.
			if len(sentence) > 4:
				try:
					if model.entropy(sentence) < len(sentence) * 5.0:
						sentence = []
						continue
				except ValueError:
					pass # infinite entropy
			
			if len(sentence) > 25:
				# sentence was too long, try again
				sentence = []
				continue
		
		return " ".join(sentence)
		
	for bill_type in ("bill", "resolution"):
		with codecs.open("data/misc/april_fools_bill_titles_%s.txt" % bill_type, "w", "utf-8") as f:
			for i in xrange(10000):
				f.write( make_random_bill_title(bill_type) + u"\n" )
	

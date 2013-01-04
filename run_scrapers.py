#!/usr/bin/python

import os, os.path, glob, re, hashlib, shutil

CONGRESS = 113
SCRAPER_PATH = "../scripts/congress"

# UTILS

def mkdir(path):
	if not os.path.exists(path):
		os.makedirs(path)

def md5(fn):
	md5 = hashlib.md5()
	md5.update(open(fn).read())
	return md5.digest()

def copy(fn1, fn2):
	# Don't copy unchanged files so that we don't touch file modification times.
	if os.path.exists(fn2):
		if md5(fn1) == md5(fn2):
			return
	print fn2
	shutil.copyfile(fn1, fn2)

# MAIN

# Prepare Paths
mkdir("data/us/%d/bills" % CONGRESS)
mkdir("data/us/%d/rolls" % CONGRESS)

# Run Scripts
os.system("cd %s; . .env/bin/activate; ./run bills --govtrack --fetch --congress=%d --loglevel=WARN" % (SCRAPER_PATH, CONGRESS))
os.system("cd %s; . .env/bin/activate; ./run votes --govtrack --fetch --congress=%d --loglevel=WARN" % (SCRAPER_PATH, CONGRESS))

# Copy files into place.

# Bills...
bill_type_map = { 'hr': 'h', 's': 's', 'hres': 'hr', 'sres': 'sr', 'hjres': 'hj', 'sjres': 'sj', 'hconres': 'hc', 'sconres': 'sc' }
for fn in glob.glob("%s/data/%d/bills/*/*/data.xml" % (SCRAPER_PATH, CONGRESS)):
	congress, bill_type, number = re.match(r".*congress/data/(\d+)/bills/([a-z]+)/(?:[a-z]+)(\d+)/data.xml$", fn).groups()
	if int(congress) != CONGRESS: raise ValueError()
	if bill_type not in bill_type_map: raise ValueError()
	fn2 = "data/us/%d/bills/%s%d.xml" % (CONGRESS, bill_type_map[bill_type], int(number))
	copy(fn, fn2)

# Votes...
for fn in glob.glob("%s/data/%d/votes/*/*/data.xml" % (SCRAPER_PATH, CONGRESS)):
	congress, session, chamber, number = re.match(r".*congress/data/(\d+)/votes/(\d+)/([hs])(\d+)/data.xml$", fn).groups()
	if int(congress) != CONGRESS: raise ValueError()
	fn2 = "data/us/%d/rolls/%s%s-%d.xml" % (CONGRESS, chamber, session, int(number))
	copy(fn, fn2)

	
# Parse.
os.system("./parse.py --congress=%d bill" % CONGRESS) #  -l ERROR
os.system("./parse.py --congress=%d vote" % CONGRESS) #  -l ERROR


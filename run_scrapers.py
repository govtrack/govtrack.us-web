#!/usr/bin/python

# ./run_scrapers.py bills votes text amendments

import os, os.path, glob, re, hashlib, shutil, sys

CONGRESS = 113
SCRAPER_PATH = "../scripts/congress"

# UTILS

def mkdir(path):
	if not os.path.exists(path):
		os.makedirs(path)

def md5(fn, modulo):
	# do an MD5 on the file but run a regex first
	# to remove content we don't want to check for
	# differences.
	
	data = open(fn).read()
	data = re.sub(modulo, data, "--")
	
	md5 = hashlib.md5()
	md5.update(data)
	return md5.digest()

def copy(fn1, fn2, modulo):
	# Don't copy unchanged files so that we don't touch file modification times.
	if os.path.exists(fn2):
		if md5(fn1, modulo) == md5(fn2, modulo):
			return
	print fn2
	shutil.copyfile(fn1, fn2)

# MAIN

# Prepare Paths
mkdir("data/us/%d" % CONGRESS)
mkdir("data/us/%d/bills" % CONGRESS)
mkdir("data/us/%d/rolls" % CONGRESS)

# Set options.

fetch_mode = "--force"
log_level = "error"

if "CACHE" in os.environ:
	fetch_mode = ""
	
# Run scrapers and parsers.

if "people" in sys.argv:
	# Convert people YAML into the legacy format.
	if CONGRESS != 113: raise ValueErrror()
	os.system("python ../scripts/legacy-conversion/convert_people.py %s/cache/congress-legislators/ data/us/people_legacy.xml data/us/people.xml 0" % SCRAPER_PATH)
	os.system("python ../scripts/legacy-conversion/convert_people.py %s/cache/congress-legislators/ data/us/people_legacy.xml data/us/%d/people.xml 1" % (SCRAPER_PATH, CONGRESS))

if "bills" in sys.argv:
	# Scrape.
	os.system("cd %s; . .env/bin/activate; ./run bills --govtrack %s --congress=%d --log=%s" % (SCRAPER_PATH, fetch_mode, CONGRESS, log_level))

	# Copy files into legacy location.
	bill_type_map = { 'hr': 'h', 's': 's', 'hres': 'hr', 'sres': 'sr', 'hjres': 'hj', 'sjres': 'sj', 'hconres': 'hc', 'sconres': 'sc' }
	for fn in glob.glob("%s/data/%d/bills/*/*/data.xml" % (SCRAPER_PATH, CONGRESS)):
		congress, bill_type, number = re.match(r".*congress/data/(\d+)/bills/([a-z]+)/(?:[a-z]+)(\d+)/data.xml$", fn).groups()
		if int(congress) != CONGRESS: raise ValueError()
		if bill_type not in bill_type_map: raise ValueError()
		fn2 = "data/us/%d/bills/%s%d.xml" % (CONGRESS, bill_type_map[bill_type], int(number))
		copy(fn, fn2, r'updated="[^"]+"')

	# Load into db.
	os.system("./parse.py --congress=%d bill" % CONGRESS) #  -l ERROR
	
if "votes" in sys.argv:
	# Scrape.
	os.system("cd %s; . .env/bin/activate; ./run votes --govtrack %s --congress=%d --log=%s" % (SCRAPER_PATH, fetch_mode, CONGRESS, log_level))
	
	# Copy files into legacy location.
	for fn in glob.glob("%s/data/%d/votes/*/*/data.xml" % (SCRAPER_PATH, CONGRESS)):
		congress, session, chamber, number = re.match(r".*congress/data/(\d+)/votes/(\d+)/([hs])(\d+)/data.xml$", fn).groups()
		if int(congress) != CONGRESS: raise ValueError()
		fn2 = "data/us/%d/rolls/%s%s-%d.xml" % (CONGRESS, chamber, session, int(number))
		copy(fn, fn2, r'updated="[^"]+"')
		
	# Load into db.
	os.system("./parse.py --congress=%d vote" % CONGRESS) #  -l ERROR

if "text" in sys.argv:
	# Scrape with legacy scraper.
	os.system("cd ../scripts/gather; perl fetchbilltext.pl FULLTEXT %d" % CONGRESS)
	os.system("cd ../scripts/gather; perl fetchbilltext.pl GENERATE %d" % CONGRESS)
	

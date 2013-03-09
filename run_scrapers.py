#!/usr/bin/python

# ./run_scrapers.py text bills votes stats

import os, os.path, glob, re, hashlib, shutil, sys

CONGRESS = 113
SCRAPER_PATH = "../scripts/congress"

# UTILS

bill_type_map = { 'hr': 'h', 's': 's', 'hres': 'hr', 'sres': 'sr', 'hjres': 'hj', 'sjres': 'sj', 'hconres': 'hc', 'sconres': 'sc' }

def mkdir(path):
	if not os.path.exists(path):
		os.makedirs(path)

def md5(fn, modulo=None):
	# do an MD5 on the file but run a regex first
	# to remove content we don't want to check for
	# differences.
	
	data = open(fn).read()
	if modulo != None: data = re.sub(modulo, "--", data)
	
	md5 = hashlib.md5()
	md5.update(data)
	return md5.digest()

def copy(fn1, fn2, modulo):
	# Don't copy true unchanged files because we want to keep
	# file contents the same so long as no real data changed.
	# When we load into our db, we use hashes to check if we
	# need to process a file. And for rsync users, don't make
	# them re-download files that have no real changes.
	if os.path.exists(fn2):
		if md5(fn1, modulo) == md5(fn2, modulo):
			return False
	print fn2
	shutil.copyfile(fn1, fn2)
	return True

# MAIN

# Set options.

fetch_mode = "--force --fast"
log_level = "error"

if "full-scan" in sys.argv: fetch_mode = "--force"
if "CACHE" in os.environ: fetch_mode = ""
	
# Run scrapers and parsers.

if "people" in sys.argv:
	if CONGRESS != 113: raise ValueErrror()
	
	# Pull latest poeple YAML.
	os.system("cd %s/cache/congress-legislators; git fetch -pq" % SCRAPER_PATH)
	os.system("cd %s/cache/congress-legislators; git merge --ff-only -q origin/master" % SCRAPER_PATH)
	
	# Convert people YAML into the legacy format.
	mkdir("data/us/%d" % CONGRESS)
	os.system("python ../scripts/legacy-conversion/convert_people.py %s/cache/congress-legislators/ data/us/people_legacy.xml data/us/people.xml 0" % SCRAPER_PATH)
	os.system("python ../scripts/legacy-conversion/convert_people.py %s/cache/congress-legislators/ data/us/people_legacy.xml data/us/%d/people.xml 1" % (SCRAPER_PATH, CONGRESS))
	
	# Load YAML (directly) into db.
	os.system("RELEASE=1 ./parse.py person") #  -l ERROR
	os.system("RELEASE=1 ./manage.py update_index -v 0 -u person person")
	#os.system("RELEASE=1 ./manage.py prune_index -u person person")
	
	# Save a fixture.
	os.system("RELEASE=1 ./manage.py dumpdata --format json person > data/db/django-fixture-people.json")

if "committees" in sys.argv:
	if CONGRESS != 113: raise ValueErrror()
	
	# Convert committee YAML into the legacy format.
	os.system("python ../scripts/legacy-conversion/convert_committees.py %s %s/cache/congress-legislators/ ../data/us/%d/committees.xml" % (SCRAPER_PATH, SCRAPER_PATH, CONGRESS))

	# Load YAML (directly) into db.
	os.system("RELEASE=1 ./parse.py -l ERROR committee")
	
	

do_bill_parse = False

if "text" in sys.argv:
	# Update the mirror of GPO FDSys.
	os.system("cd %s; . .env/bin/activate; ./run fdsys --collections=BILLS --store=mods --log=%s" % (SCRAPER_PATH, log_level))
	
	def do_text_file(src, dest):
		if not os.path.exists(dest):
			print "missing", src, dest
			os.link(src, dest)
		elif os.stat(src).st_ino == os.stat(dest).st_ino:
			pass # files are the same (hardlinked)
		else:
			if md5(src) != md5(dest):
				print "replacing", src, dest
			else:
				print "squashing existing file", src, dest
			os.unlink(dest)
			os.link(src, dest)
	
	# Glob all of the bill text files. Create hard links in the data directory to
	# their locations in the congress project data directoy.
	for congress in xrange(CONGRESS, CONGRESS+1): # we should start at 103 in case GPO has made changes to past files, but it takes so long!
		mkdir("data/us/bills.text/%d" % CONGRESS)
		for bt in bill_type_map.values():
			mkdir("data/us/bills.text/%d/%s" % (CONGRESS, bt))
		
		for bill in sorted(glob.iglob("%s/data/%d/bills/*/*" % (SCRAPER_PATH, congress))):
			bill_type, bill_number = re.match(r"([a-z]+)(\d+)$", os.path.basename(bill)).groups()
			bill_type = bill_type_map[bill_type]
			for ver in sorted(glob.iglob(bill + "/text-versions/*")):
				if ".json" in ver: continue # .json metadata files
				basename = "../data/us/bills.text/%d/%s/%s%s%s." % (congress, bill_type, bill_type, bill_number, os.path.basename(ver))
				do_text_file(ver + "/mods.xml", basename + "mods.xml")
	
	# Now do the old-style scraper (except mods files) because it handles
	# making symlinks to the latest version of each bill. And other data
	# types, like XML.

	# Scrape with legacy scraper.
	# Do this before bills because the process of loading into the db checks for new
	# bill text and generates feed events for text availability.
	os.system("cd ../scripts/gather; perl fetchbilltext.pl FULLTEXT %d" % CONGRESS)
	os.system("cd ../scripts/gather; perl fetchbilltext.pl GENERATE %d" % CONGRESS)
	do_bill_parse = True # don't know if we got any new files
	
if "bills" in sys.argv:
	# Scrape.
	os.system("cd %s; . .env/bin/activate; ./run bills --govtrack %s --congress=%d --log=%s" % (SCRAPER_PATH, fetch_mode, CONGRESS, log_level))
	
	# Copy files into legacy location.
	mkdir("data/us/%d/bills" % CONGRESS)
	bill_type_map = { 'hr': 'h', 's': 's', 'hres': 'hr', 'sres': 'sr', 'hjres': 'hj', 'sjres': 'sj', 'hconres': 'hc', 'sconres': 'sc' }
	for fn in sorted(glob.glob("%s/data/%d/bills/*/*/data.xml" % (SCRAPER_PATH, CONGRESS))):
		congress, bill_type, number = re.match(r".*congress/data/(\d+)/bills/([a-z]+)/(?:[a-z]+)(\d+)/data.xml$", fn).groups()
		if int(congress) != CONGRESS: raise ValueError()
		if bill_type not in bill_type_map: raise ValueError()
		fn2 = "data/us/%d/bills/%s%d.xml" % (CONGRESS, bill_type_map[bill_type], int(number))
		do_bill_parse |= copy(fn, fn2, r'updated="[^"]+"')
		
	# TODO: Even if we didn't get any new files, the bills parser also
	# scrapes docs.house.gov and the Senate floor schedule, so we should
	# also periodically make sure we run the scraper for that too.

if do_bill_parse:
	# Load into db.
	os.system("RELEASE=1 ./parse.py --congress=%d bill" % CONGRESS) #  -l ERROR

	# bills and state bills are indexed as they are parsed, but to
	# freshen the index... Because bills index full text and so
	# indexing each time is substantial, set the TIMEOUT and
	# BATCH_SIZE options in the haystack connections appropriately.
	# ./manage.py update_index -v 2 -u bill bill

if "amendments" in sys.argv:
	# Scrape.
	os.system("cd %s; . .env/bin/activate; ./run amendments --govtrack %s --congress=%d --log=%s" % (SCRAPER_PATH, fetch_mode, CONGRESS, log_level))

	# Copy files into legacy location.
	mkdir("data/us/%d/bills.amdt" % CONGRESS)
	for fn in sorted(glob.glob("%s/data/%d/amendments/*/*/data.xml" % (SCRAPER_PATH, CONGRESS))):
		congress, chamber, number = re.match(r".*congress/data/(\d+)/amendments/([hs])amdt/(?:[hs])amdt(\d+)/data.xml$", fn).groups()
		if int(congress) != CONGRESS: raise ValueError()
		fn2 = "data/us/%d/bills.amdt/%s%d.xml" % (CONGRESS, chamber, int(number))
		copy(fn, fn2, r'updated="[^"]+"')
		
	# TODO: Load into db when we have a modle for it?

if "votes" in sys.argv:
	# Scrape.
	os.system("cd %s; . .env/bin/activate; ./run votes --govtrack %s --congress=%d --log=%s" % (SCRAPER_PATH, fetch_mode, CONGRESS, log_level))
	
	# Copy files into legacy location.
	did_any_file_change = False
	mkdir("data/us/%d/rolls" % CONGRESS)
	for fn in sorted(glob.glob("%s/data/%d/votes/*/*/data.xml" % (SCRAPER_PATH, CONGRESS))):
		congress, session, chamber, number = re.match(r".*congress/data/(\d+)/votes/(\d+)/([hs])(\d+)/data.xml$", fn).groups()
		if int(congress) != CONGRESS: raise ValueError()
		fn2 = "data/us/%d/rolls/%s%s-%d.xml" % (CONGRESS, chamber, session, int(number))
		did_any_file_change |= copy(fn, fn2, r'updated="[^"]+"')
		
	# Load into db.
	if did_any_file_change:
		os.system("RELEASE=1 ./parse.py --congress=%d vote" % CONGRESS) #  -l ERROR

if "stats" in sys.argv:
	os.system("cd analysis; python sponsorship_analysis.py %d" % CONGRESS)
	os.system("cd analysis; python missed_votes.py %d" % CONGRESS)
	
if "historical_bills" in sys.argv:
	# Pull in statutes from the 85th-92nd Congress
	# via the GPO's Statutes at Large.
	
	os.system("cd %s; . .env/bin/activate; ./run fdsys --collections=STATUTE --store=mods --log=%s" % (SCRAPER_PATH, "warn")) # log_level
	os.system("cd %s; . .env/bin/activate; ./run statutes --volumes=65-86 --log=%s" % (SCRAPER_PATH, "warn")) # log_level
	
	for congress in xrange(82, 92+1):
		print congress, "..."
		
		# Copy files into legacy location.
		mkdir("data/us/%d/bills" % congress)
		for fn in sorted(glob.glob("%s/data/%d/bills/*/*/data.xml" % (SCRAPER_PATH, congress))):
			bill_type, number = re.match(r".*congress/data/\d+/bills/([a-z]+)/(?:[a-z]+)(\d+)/data.xml$", fn).groups()
			if bill_type not in bill_type_map: raise ValueError()
			fn2 = "data/us/%d/bills/%s%d.xml" % (congress, bill_type_map[bill_type], int(number))
			copy(fn, fn2, r'updated="[^"]+"')
			
		# Load into db.
		os.system("RELEASE=1 ./parse.py --congress=%d bill" % congress) #  -l ERROR
		

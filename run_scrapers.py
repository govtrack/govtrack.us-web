#!script

# ./run_scrapers.py text bills votes stats

import os, os.path, glob, re, hashlib, shutil, sys, datetime

CONGRESS = int(os.environ.get("CONGRESS", "115"))
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
	
	with open(fn) as fobj:
		data = fobj.read()
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
	#print fn2
	shutil.copy2(fn1, fn2)
	return True

def make_link(src, dest):
	if not os.path.exists(dest):
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

# MAIN

# Set options.

log_level = "error"
if "DEBUG" in os.environ: log_level = "info"
	
# Run scrapers and parsers.

if "people" in sys.argv:
	if CONGRESS != 115: raise ValueErrror()
	
	# Pull latest poeple YAML.
	os.system("cd %s/congress-legislators; git fetch -pq" % SCRAPER_PATH)
	os.system("cd %s/congress-legislators; git merge --ff-only -q origin/master" % SCRAPER_PATH)
	
	# Convert people YAML into alternative formats.
	os.system("cd %s/congress-legislators/scripts; . .env/bin/activate; python alternate_bulk_formats.py" % SCRAPER_PATH)

	# Copy into our public directory.
	for f in glob.glob("%s/congress-legislators/*.yaml" % SCRAPER_PATH):
		make_link(f, "data/congress-legislators/%s" % os.path.basename(f))
	for f in glob.glob("%s/congress-legislators/alternate_formats/*.csv" % SCRAPER_PATH):
		make_link(f, "data/congress-legislators/%s" % os.path.basename(f))

	# Load YAML (directly) into db.
	os.system("./parse.py person") #  -l ERROR
	os.system("./manage.py update_index -v 0 -u person person")
	#os.system("./manage.py prune_index -u person person")
	
	# Save a fixture.
	os.system("./manage.py dumpdata --format json person > data/db/django-fixture-people.json")

if "committees" in sys.argv:
	if CONGRESS != 115: raise ValueErrror()
	
	# Committee metadata.
	
	# Pull latest YAML.
	os.system("cd %s/congress-legislators; git fetch -pq" % SCRAPER_PATH)
	os.system("cd %s/congress-legislators; git merge --ff-only -q origin/master" % SCRAPER_PATH)
	
	# Committee events.
	os.system("cd %s; . .env/bin/activate; ./run committee_meetings --docs=False --log=%s" % (SCRAPER_PATH, log_level))
	
	# Load into db.
	os.system("./parse.py -l ERROR committee")

	# Generate historical XML, used by prognosis & session stats.
	os.system("cd ../scripts/legacy-conversion; . ../%s/congress-legislators/scripts/.env/bin/activate; python convert_committees.py ../%s/congress-legislators/ ../data/historical-committee-membership/%s.xml"
		% (SCRAPER_PATH, SCRAPER_PATH, CONGRESS))

	# Save a fixture.
	os.system("./manage.py dumpdata --format json committee.Committee committee.CommitteeMember > data/db/django-fixture-committees.json")

do_bill_parse = False

if "text" in sys.argv:
	# Do this before bills because the process of loading into the db checks for new
	# bill text and generates feed events for text availability.

	# Update the mirror of bill text on GPO FDSys, except PDFs.
	os.system("cd %s; . .env/bin/activate; ./run fdsys --collections=BILLS --bulkdata=False --store=mods,text,xml --log=%s" % (SCRAPER_PATH, log_level))

	# Fetch PDFs. We do this separately because we only use them for thumbnails and
	# don't want to expose in data.
	os.system("(cd ~/scripts/congress-pdf-config/; . .env/bin/activate; ./run fdsys --collections=BILLS --bulkdata=False --store=pdf --log=%s)" % log_level)

	# Also metadata for committee reports, for the current Congress (because we
	# only use this for 114th forward).
	os.system("(cd ~/scripts/congress-pdf-config/; . .env/bin/activate; ./run fdsys --collections=CRPT --store=mods --congress=%s --log=%s)" % (CONGRESS, log_level))

	# Update the mirror of Cato's deepbills.
	os.system("cd %s; . .env/bin/activate; ./run deepbills --log=%s" % (SCRAPER_PATH, log_level))

	# Update text incorporation analysis for any new text versions.
	os.system("analysis/text_incorporation.py analyze %d" % CONGRESS)
	os.system("analysis/text_incorporation.py load %d" % CONGRESS)
	
	# don't know if we got any new files, so assume we now need to update bills
	do_bill_parse = True
	
if "bills" in sys.argv:
	# Scrape.
	if CONGRESS >= 114:
		os.system("cd %s; . .env/bin/activate; ./run fdsys --bulkdata=True --collections=BILLSTATUS --log=%s; ./run bills --govtrack --congress=%d --log=%s" % (SCRAPER_PATH, log_level, CONGRESS, log_level))
	
	# Copy files into legacy location.

	mkdir("data/us/%d/bills" % CONGRESS)
	bill_type_map = { 'hr': 'h', 's': 's', 'hres': 'hr', 'sres': 'sr', 'hjres': 'hj', 'sjres': 'sj', 'hconres': 'hc', 'sconres': 'sc' }
	for fn in sorted(glob.glob("%s/data/%d/bills/*/*/data.xml" % (SCRAPER_PATH, CONGRESS))):
		congress, bill_type, number = re.match(r".*congress/data/(\d+)/bills/([a-z]+)/(?:[a-z]+)(\d+)/data.xml$", fn).groups()
		if int(congress) != CONGRESS: raise ValueError()
		if bill_type not in bill_type_map: raise ValueError()
		fn2 = "data/us/%d/bills/%s%d.xml" % (CONGRESS, bill_type_map[bill_type], int(number))
		do_bill_parse |= copy(fn, fn2, r'updated="[^"]+"')

	mkdir("data/us/%d/bills.amdt" % CONGRESS)
	for fn in sorted(glob.glob("%s/data/%d/amendments/*/*/data.xml" % (SCRAPER_PATH, CONGRESS))):
		congress, amdt_type, number = re.match(r".*congress/data/(\d+)/amendments/([hsup]+)amdt/(?:[hsup]+)amdt(\d+)/data.xml$", fn).groups()
		if int(congress) != CONGRESS: raise ValueError()
		fn2 = "data/us/%d/bills.amdt/%s%d.xml" % (CONGRESS, amdt_type, int(number))
		copy(fn, fn2, r'updated="[^"]+"')
	
	# Scrape upcoming House bills.

	os.system("cd %s; . .env/bin/activate; ./run upcoming_house_floor --log=%s" % (SCRAPER_PATH, log_level))
	do_bill_parse = True
	
	# os.system("./manage.py dumpdata --format json bill.BillTerm > data/db/django-fixture-billterms.json")

if do_bill_parse:
	# Load into db.
	os.system("./parse.py --congress=%d -l %s bill" % (CONGRESS, log_level))
	os.system("./parse.py --congress=%d -l %s amendment" % (CONGRESS, log_level))

	# bills are indexed as they are parsed, but to
	# freshen the index... Because bills index full text and so
	# indexing each time is substantial, set the TIMEOUT and
	# BATCH_SIZE options in the haystack connections appropriately.
	# ./manage.py update_index -v 2 -u bill bill

if "votes" in sys.argv:
	# Scrape.
	if CONGRESS >= 101:
		os.system("cd %s; . .env/bin/activate; ./run votes --govtrack --log=%s --force --fast" % (SCRAPER_PATH, log_level))
	
	# Copy files into legacy location.
	did_any_file_change = False
	mkdir("data/us/%d/rolls" % CONGRESS)
	for fn in sorted(glob.glob("%s/data/%d/votes/*/*/data.xml" % (SCRAPER_PATH, CONGRESS))):
		congress, session, chamber, number = re.match(r".*congress/data/(\d+)/votes/(\d+|[A-C])/([hs])(\d+)/data.xml$", fn).groups()
		if int(congress) != CONGRESS: raise ValueError()
		fn2 = "data/us/%d/rolls/%s%s-%d.xml" % (CONGRESS, chamber, session, int(number))
		did_any_file_change |= copy(fn, fn2, r'updated="[^"]+"')
		
	# Load into db.
	if did_any_file_change or True: # amendments can mark votes as missing data
		os.system("./parse.py vote --congress=%d -l %s" % (CONGRESS, log_level))

	# Update key votes analysis.
	os.system("analysis/key_votes.py %d" % CONGRESS)

	# Update change tracker.
	os.system("/home/govtrack/update-votes-servo")

	# During election season.
	#os.system("analysis/missed_votes_prezcandidates.py > /tmp/votes-$$.json && mv /tmp/votes-$$.json data/misc/presidential-candidates-missed-votes.json")

if "stats" in sys.argv:
	os.system("analysis/sponsorship_analysis.py %d" % CONGRESS)
	os.system("analysis/missed_votes.py %d" % CONGRESS)
	
if "am_mem_bills" in sys.argv:
	# American Memory
	os.syste("for c in {6..42}; do echo $c; ./parse.py bill --force --congress=$c --level=warn; done")
	
if "stat_bills" in sys.argv:
	# Pull in statutes from the 85th-92nd Congress
	# via the GPO's Statutes at Large.
	
	os.system("cd %s; . .env/bin/activate; ./run fdsys --collections=STATUTE --store=mods --log=%s" % (SCRAPER_PATH, "warn")) # log_level
	os.system("cd %s; . .env/bin/activate; ./run statutes --volumes=65-86 --log=%s" % (SCRAPER_PATH, "warn")) # log_level
	os.system("cd %s; . .env/bin/activate; ./run statutes --volumes=87-106 --textversions --log=%s" % (SCRAPER_PATH, "warn")) # log_level
	
	# Copy bill metadata into our legacy location.
	# (No need to copy text-versions anywhere: we read it from the congress data directory.)
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
		os.system("./parse.py --congress=%d bill" % congress) #  -l ERROR
		
if "photos" in sys.argv:
	# Pull in any new photos from the unitedstates/images repository.

	import person.models, os, shutil, yaml

	#os.system("cd ../scripts/congress-images; git pull --rebase")

	src = '../scripts/congress-images/congress/original/'
	dst = 'data/photos/'

	# Get a list of GovTrack IDs and Bioguide IDs for which photos are provided
	# in the unitedstates/images repo. Only import photos of current Members of
	# Congress because I haven't reviewed older photos necessarily.
	bioguide_ids = [f[len(src):-4] for f in glob.glob(src + '*.jpg')]
	id_pairs = person.models.Person.objects.filter(
		bioguideid__in=bioguide_ids,
		roles__current=True)\
		.values_list('id', 'bioguideid')

	for govtrack_id, bioguide_id in id_pairs:
		# source JPEG & sanity check that it exists
		fn1 = src + bioguide_id + ".jpg"
		if not os.path.exists(fn1):
			print "Missing: " + fn1
			continue

		# destination file name
		fn2 = dst + str(govtrack_id) + ".jpeg"

		# need to review?
		if not (os.path.exists(fn2) and md5(fn1) == md5(fn2)):
			p = person.models.Person.objects.get(id=govtrack_id)
			r = p.roles.get(current=True)
			print ("change" if os.path.exists(fn2) else "new"), p
			print "<hr><p>%s</p>" % p.name.encode("utf8")
			print("<table cols=2><tr>")
			if os.path.exists(fn2):
				print "<td><img src='https://www.govtrack.us/data/photos/%d.jpeg'></td>" % p.id
			else:
				print "<iframe src='%s' width=100%% height=500> </iframe>" % ("https://twitter.com/"+p.twitterid if p.twitterid else r.website)
			print "<td><img src='https://raw.githubusercontent.com/unitedstates/images/newscraper/congress/original/%s.jpg'></td>" % bioguide_id
			print "</tr></table>"
			metadata = yaml.load(open(fn1.replace("/original/", "/metadata/").replace(".jpg", ".yaml")))
			print "<p>%s</p><p>%s</p>" % (metadata['link'], metadata['name'])
			continue

		# check if the destination JPEG already exists and it has different content
		if os.path.exists(fn2) and md5(fn1) != md5(fn2):
			# Back up the existing files first. If we already have a backed up
			# image, don't overwrite the back up. Figure out what to do another
			# time and just bail now. Check that we won't overwrite any files
			# before we attempt to move them.
			def get_archive_fn(fn):
				return fn.replace("/photos/", "/photos/archive/")
			files_to_archive = [fn2] + glob.glob(fn2.replace(".jpeg", "-*"))
			for fn in files_to_archive:
				if os.path.exists(get_archive_fn(fn)):
				 	raise ValueError("Archived photo already exists: " + fn)

			# Okay now actually do the backup.
			for fn in files_to_archive:
				print fn, "=>", get_archive_fn(fn)
				shutil.move(fn, get_archive_fn(fn))

		# Copy in the file if it's new.
		if copy(fn1, fn2, None):
			print fn1, "=>", fn2

			# get required metadata
			metadata = yaml.load(open(fn1.replace("/original/", "/metadata/").replace(".jpg", ".yaml")))
			if metadata.get("name", "").strip() == "": raise ValueError("Metadata is missing name.")
			if metadata.get("link", "").strip() == "": raise ValueError("Metadata is missing link.")

			# Write the metadata.
			with open(fn2.replace(".jpeg", "-credit.txt"), "w") as credit_file:
				credit_file.write( (metadata.get("link", "").strip() + " " + metadata.get("name", "").strip() + "\n").encode("utf-8") )
	
			# Generate resized versions.
			for size_width in (50, 100, 200):
				size_height = int(round(size_width * 1.2))
				os.system("convert %s -resize %dx%d^ -gravity center -extent %dx%d %s"
					% (fn2, size_width, size_height, size_width, size_height,
						fn2.replace(".jpeg", ("-%dpx.jpeg" % size_width)) ))

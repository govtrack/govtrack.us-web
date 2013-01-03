#!/usr/bin/python

import os, os.path, glob, re, hashlib, shutil

CONGRESS = 113

def md5(fn):
	md5 = hashlib.md5()
	md5.update(open(fn).read())
	return md5.digest()

def mkdir(path):
	if not os.path.exists(path):
		os.makedirs(path)
		
# Prepare Paths
mkdir("data/us/%d/bills" % CONGRESS)
mkdir("data/us/%d/rolls" % CONGRESS)

# Run Scripts
os.system("cd ../scripts/congress; . .env/bin/activate; ./run votes --govtrack --fetch --congress=%d --loglevel=WARN" % CONGRESS)

# Copy files into place.

# Votes...
for fn in glob.glob("congress/data/%d/votes/*/*/*.xml" % CONGRESS):
	congress, session, chamber, number = re.match(r"congress/data/(\d+)/votes/(\d+)/([hs])(\d+)/data.xml$", fn).groups()
	if int(congress) != CONGRESS: raise ValueError()
	fn2 = "data/us/%d/rolls/%s%s-%d.xml" % (CONGRESS, chamber, session, int(number))

	# Don't copy unchanged files so that we don't touch file modification times.
	if os.path.exists(fn2):
		if md5(fn) == md5(fn2):
			continue
	
	print fn2
	shutil.copyfile(fn, fn2)
	
# Parse.
os.system("./parse.py --congress=%d vote" % CONGRESS) #  -l ERROR


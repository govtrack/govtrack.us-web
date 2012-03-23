#!/usr/bin/python

# Download and unzip ftp://ftp.census.gov/geo/tiger/TIGER2011/CD/tl_2011_us_cd112.zip
# into ../extdata/gis/national.

import sys, os
sys.path.insert(0, "..")
sys.path.insert(0, ".")
os.environ["DJANGO_SETTINGS_MODULE"] = "settings"

import settings
import pickle
import base64
import shpUtils

from django.db import connection
import settings

state_fips_codes = {
	1: "AL", 2: "AK", 4: "AZ", 5: "AR", 6: "CA", 8: "CO", 9: "CT",
	10: "DE", 11: "DC", 12: "FL", 13: "GA", 15: "HI", 16: "ID", 17: "IL",
	18: "IN", 19: "IA", 20: "KS", 21: "KY", 22: "LA", 23: "ME", 24: "MD",
	25: "MA", 26: "MI", 27: "MN", 28: "MS", 29: "MO", 30: "MT", 31: "NE",
	32: "NV", 33: "NH", 34: "NJ", 35: "NM", 36: "NY", 37: "NC", 38: "ND",
	39: "OH", 40: "OK", 41: "OR", 42: "PA", 44: "RI", 45: "SC", 46: "SD",
	47: "TN", 48: "TX", 49: "UT", 50: "VT", 51: "VA", 53: "WA", 54: "WV",
	55: "WI", 56: "WY", 60: "AS", 66: "GU", 69: "MP", 72: "PR", 78: "VI"
	}

states_in_shp = set()
	
cursor = connection.cursor()
try:
	cursor.execute("DROP TABLE IF EXISTS districtpolygons_")
except:
	# even though it has IF EXISTS, a warning is being generated that busts everything
	pass
cursor.execute("CREATE TABLE districtpolygons_ (state VARCHAR(2), district TINYINT, bbox POLYGON NOT NULL, pointspickle LONGTEXT)")
cursor.execute("CREATE INDEX state_district_index ON districtpolygons_ (state, district)")
cursor.execute("CREATE SPATIAL INDEX bbox_index ON districtpolygons_ (bbox)")

shpRecords = shpUtils.loadShapefile("../extdata/gis/national/tl_2011_us_cd112.shp")
for district in shpRecords["features"]:
	state = state_fips_codes[int(district["info"]["STATEFP"])]
	cd = int(district["info"]["CD112FP"])
	if cd in (98, 99):
		cd = 0
		
	for part in district["shape"]["parts"]:
		print state, cd, part["bounds"]
		states_in_shp.add(state)
		cursor.execute("INSERT INTO districtpolygons_ VALUES(%s, %s, GeomFromText('POLYGON((%s %s, %s %s, %s %s, %s %s, %s %s))'), %s)",
			[state, cd,
			 part["bounds"][0][0], part["bounds"][0][1],
			 part["bounds"][1][0], part["bounds"][0][1],
			 part["bounds"][1][0], part["bounds"][1][1],
			 part["bounds"][0][0], part["bounds"][1][1],
			 part["bounds"][0][0], part["bounds"][0][1],
			 base64.b64encode(pickle.dumps(part["points"]))])

for state in state_fips_codes.values():
	if not state in states_in_shp:
		print "No data for", state, "!"

try:
	cursor.execute("DROP TABLE IF EXISTS istrictpolygons")
except:
	# again, a warning is causing problems even though we have IF NOT EXISTS
	pass
cursor.execute("RENAME TABLE districtpolygons_ TO districtpolygons")


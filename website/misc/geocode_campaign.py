#!.env/bin/python

import sys, os, time
sys.path.insert(0, "..")
sys.path.insert(0, ".")
os.environ["DJANGO_SETTINGS_MODULE"] = "settings"

from settings import GEOCODERUS_USERNAME, GEOCODERUS_PASSWORD

from website.models import CampaignSupporter
from person.views import do_district_lookup

def geocode(c):
	import urllib, urllib2, csv, base64
	
	address = "%s, %s, %s %s" % (c.address, c.city, c.state, c.zipcode)
	
	url = "http://geocoder.us/member/service/csv/geocode?" + urllib.urlencode({ "address": address.encode("utf8") })
	req = urllib2.Request(url)
	req.add_header("Authorization", "Basic %s" % base64.encodestring('%s:%s' % (GEOCODERUS_USERNAME, GEOCODERUS_PASSWORD))[:-1])
		
	r = urllib2.urlopen(req)
	for line in csv.reader(r):
		if line[0] == "2: couldn't find this address! sorry":
			return "NOT FOUND"
		return { "lat": float(line[0]), "lng": float(line[1]) }
	return None

for c in CampaignSupporter.objects.all():
	if c.geocode_response == None:
		c.geocode_response = repr(geocode(c))
		c.save()
	if eval(c.geocode_response) not in (None, "NOT FOUND") and c.district == None:
		coord = eval(c.geocode_response)
		distr = do_district_lookup(coord["lng"], coord["lat"])
		if distr != None and "error" not in distr:
			c.state = distr["state"] # people entered the first two letters of the full state name, geocoder is figuring it out
			c.district = distr["district"]
			c.save()


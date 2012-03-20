#!.env/bin/python

raise Exception("We should not run this again. It destroys data.")

import sys, os
sys.path.insert(0, "..")
sys.path.insert(0, ".")
os.environ["DJANGO_SETTINGS_MODULE"] = "web.settings"

from django.contrib.auth.models import User
from django.core.validators import validate_email
import csv
from datetime import datetime

from events.models import Feed
from bill.models import BillTerm
from committee.models import Committee

committee_map = { }
from lxml import etree
for c in etree.parse("data/us/committees.xml").xpath("committee[not(@obsolete=1)]"):
	for n in c.xpath("thomas-names/name"):
		committee_map[n.text] = c.get("code")
		for s in c.xpath("subcommittee"):
			for n2 in s.xpath("thomas-names/name"):
				committee_map[n.text + " -- " + n2.text] = c.get("code") + s.get("code")

crs_map = {
	"Internet": "Internet and video services",
	"Homosexuality": "Sex, gender, sexual orientation discrimination",
	"Sexual orientation": "Sex, gender, sexual orientation discrimination",
	"Identity theft": "Computer security and identity theft",	
	"Marijuana": "Drug trafficking and controlled substances",
	"Computer crimes and identity theft": "Computer security and identity theft",
	"Financial crises and failures": "Financial crises and stabilization",
	"Health information systems": "Health information and medical records",
	"Methamphetamine": "Drug trafficking and controlled substances",
	"Interest and interest rates": "Interest",
}

feed_cache = { }
missing_feeds = { }

header = None
for line in csv.reader(sys.stdin, delimiter="\t"):
	if not header:
		header = line
		continue
	
	fields = dict(zip(header, line))
	user, isnew = User.objects.get_or_create(
		username=fields["email"].strip()[0:30],
		email=fields["email"].strip(),
		defaults = {
			"date_joined": fields["created"],
			"last_login": fields["last_login"],
		})
	prof = user.userprofile()
	if isnew:
		user.set_password(fields["password"])
		user.save()
		
		prof.old_id = fields["id"]
		prof.massemail = fields["massemail"]
		prof.save()
		
	if fields["monitors"].strip() == "":
		continue
		
	sublist = prof.lists().get(is_default=True)
	sublist.trackers.clear()
	sublist.email = fields["emailupdates"] # happens to be the same coding
	sublist.last_event_mailed = None
	sublist.save()

	for m in fields["monitors"].split(","):
		if m in ("", "option:relatedblogs"): continue
		m = m.replace("%COMMA%", ",");
		m = m.replace("\\;", ";");
		m = m.replace("\\\\", "\\");
		m = m.replace("$/", "\\");
		m = m.replace("$;", ",");
		m = m.replace("$C", ",");
		m = m.replace("$$", "$");
		m = m.replace(r"\\;", ",").replace(r"\;", ",")
		try:
			if m in feed_cache:
				feed = feed_cache[m]
			elif m.startswith("crs:"):
				name = m[4:]
				name = crs_map.get(name, name)
				terms = BillTerm.objects.filter(name=m[4:]).order_by("-term_type") # new first
				if len(terms) > 0:
					feed = Feed.IssueFeed(terms[0])
				else:
					raise ValueError("unknown subject")
			elif m.startswith("committee:"):
				m = m[10:].replace(" Subcommittee", "").replace("  ", " ")
				feed = Feed.CommitteeFeed(Committee.objects.get(code=committee_map[m]))
			else:
				feed = Feed.from_name(m)
			feed_cache[m] = feed
			
			sublist.trackers.add(feed)
			
		except Exception as e:
			#print fields["id"], m, e
			missing_feeds[m] = missing_feeds.get(m, 0) + 1
	
#print sorted((v, k) for k, v in missing_feeds.items())


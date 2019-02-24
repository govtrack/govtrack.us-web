#!/usr/bin/env python

import sys
from datetime import datetime
from lxml import etree
import rtyaml

###

LEGISLATORS_PATH = sys.argv[1]
NEW_COMMITTEE_FILE = sys.argv[2]

# Make an ID map.

govtrack_person_id_map = {}
for moc in rtyaml.load(open(LEGISLATORS_PATH + "/legislators-current.yaml")):
	govtrack_person_id_map[moc['id']['bioguide']] = str(moc['id']['govtrack']) # needs to be str for XML output
	
# Load committee data.
committees = rtyaml.load(open(LEGISLATORS_PATH + "/committees-current.yaml"))
members = rtyaml.load(open(LEGISLATORS_PATH + "/committee-membership-current.yaml"))

# Generate.
new_committees = etree.Element( "committees" )
new_committees.text = "\n\t"
for committee in committees:
	c = etree.Element( "committee" )

	c.set( "type", committee["type"] )
	c.set( "code", committee["thomas_id"] )
	c.set( "displayname", committee["name"] )

	if committee["thomas_id"] not in members:
		print("Warning: No committee members:", committee["thomas_id"])
		
	for member in members.get(committee["thomas_id"], []):
		m = etree.Element( "member" )

		m.set( "id", govtrack_person_id_map[member["bioguide"]] )

		if "title" in member:
			m.set( "role", member["title"] )

		m.tail = "\n\t\t"

		c.append( m )

	if "subcommittees" in committee:
		c.text = "\n\t\t"

		for subcommittee in committee["subcommittees"]:
			sc = etree.Element( "subcommittee" )

			sc.set( "code", subcommittee["thomas_id"] )
			sc.set( "displayname", subcommittee["name"] + " Subcommittee" )

			sc.text = "\n\t\t\t"

			for member in members.get(committee["thomas_id"] + subcommittee["thomas_id"], []):
				sm = etree.Element( "member" )

				sm.set( "id", govtrack_person_id_map[member["bioguide"]] )

				if "title" in member:
					sm.set( "role", member["title"] )

				sm.tail = "\n\t\t\t"

				sc.append( sm )

			if len(sc) > 0: sc[-1].tail = "\n\t\t"

			sc.tail = "\n\t\t"

			c.append( sc )

		c[-1].tail = "\n\t"

	c.tail = "\n\t"

	new_committees.append( c )

new_committees[-1].tail = "\n"

print("Writing XML to file...")

etree.ElementTree( new_committees ).write( NEW_COMMITTEE_FILE, encoding="utf-8" )

print("Done.")


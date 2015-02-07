import sys, codecs, urllib.request, csv, json, yaml

# helper function for making web requests
utf8decoder = codecs.getreader('utf8')
def http_open(url):
	# Get the content via HTTP and decode UTF-8. Returns a stream.
	response = urllib.request.urlopen(url)
	return utf8decoder(response)

# helper function to construct a name
# Based on:
# https://github.com/govtrack/govtrack.us-web/blob/master/person/name.py
def build_name(p):
	firstname = p['name']['first']
	if firstname.endswith('.') and p['name'].get('middle'):
		firstname = p['name']['middle']
	if p['name'].get('nickname') and len(p['name']['nickname']) < len(firstname):
			firstname = p['name']['nickname']
	lastname = p['name']['last']
	if p['name'].get('suffix'):
		lastname += ' ' + p['name']['suffix']
	return firstname + ' ' + lastname

# Open output CSV file and write header.
output = csv.writer(sys.stdout)
output.writerow([
	'congress',
	'chamber',
	'analysis_start',
	'analysis_end',
	'govtrack_id',
	'bioguide_id',
	'name_short',
	'name_long',
	'birthday',
	'gender',
	'party',
	'state',
	'district',
	'leadership',
	'ideology',
	])

# Pre-load legislator data and make a mapping from ID to the
# legislator's info. We'll need this to get state & district
# info (faster than querying GovTrack's API).
legislators = { }
for fn in ('current', 'historical'):
	legdata = yaml.load(http_open("https://www.govtrack.us/data/congress-legislators/legislators-%s.yaml" % fn))
	for legislator in legdata:
		legislators[legislator['id']['govtrack']] = legislator

# Slurp in GovTrack's sponsorship analysis. Skip the 93rd Congress
# because it won't have as much data as the others.
for congress in range(94, 113+1):
	for chamber in ('h', 's'):
		print(congress, chamber, '...', file=sys.stderr)

		cmeta = json.load(http_open("https://www.govtrack.us/data/us/%d/stats/sponsorshipanalysis_%s_meta.txt" % (congress, chamber)))
		cdata = csv.DictReader(http_open("https://www.govtrack.us/data/us/%d/stats/sponsorshipanalysis_%s.txt" % (congress, chamber)))

		# For each legislator in the file...
		for row in cdata:
			# fix GovTrack's awful column headers
			row = { k.strip(): v for k, v in row.items() }

			# who is this?
			legislator = legislators[int(row['ID'])]

			# what term is this? most recent term that started before the end date of the analysis
			term = None
			for t in legislator['terms']:
				if t['type'] == ('rep' if chamber == 'h' else 'sen') \
					and t['start'] < cmeta['end_date']:
					term = t
			if not term:
				# Re-do and allow a start date the same as the analysis end date
				for t in legislator['terms']:
					if t['type'] == ('rep' if chamber == 'h' else 'sen') \
						and t['start'] <= cmeta['end_date']:
						term = t
			if not term:
				print(congress, chamber, cmeta, file=sys.stderr)
				print(row, file=sys.stderr)
				raise ValueError("Could not find term.")
			if term['party'] != row['party'].strip():
				raise ValueError(row)

			# write a row in output
			output.writerow([
				congress,
				chamber,
				cmeta['start_date'],
				cmeta['end_date'],
				int(row['ID']),
				legislator['id']['bioguide'],
				row['name'].strip(),
				build_name(legislator),
				legislator['bio'].get('birthday', ''),
				legislator['bio']['gender'],
				term['party'],
				term['state'],
				term['district'] if chamber == 'h' else '',
				float(row['leadership']),
				float(row['ideology']),
			])

# Scan the access log for who is linking to bills and accumulate
# a list of links by bill, and for search term keywords. You'll
# probably run in a cron job using:
#
# tail -200000 ../logs/access_log|./manage.py scan_accesslog 5

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from optparse import make_option

import sys, re, urlparse, urllib, lxml, apachelog

from bill.models import Bill, BillType, BillLink

re_bill = re.compile(r"^/congress/bills/(\d\d\d)/([a-z]+)([0-9]+)")

logformat = r'%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"'

class AppURLopener(urllib.FancyURLopener):
	version = "GovTrack.us scraper" # else Wikipedia gives 403s
urllib._urlopener = AppURLopener()


class Command(BaseCommand):
	args = 'minhits'
	help = 'Scans the Apache access log for referrer information to create BillLink instances. Send recent access log entries to this script by piping it into standard input.'
	
	def handle(self, *args, **options):
		if len(args) != 1:
			print "Missing argument."
			return

		min_count = int(args[0])

		p = apachelog.parser(logformat)
		
		spider = { }
		
		for line in sys.stdin:
			# Parse the acess log line.
			try:
				data = p.parse(line)
			except:
				continue
			
			# Is it a request to a bill page?
			path = data["%r"].split(" ")[1]
			m = re_bill.match(path)
			if not m: continue
			
			# Who is the referrer?
			ref = data["%{Referer}i"]
			if ref in ("", "-") or "govtrack.us" in ref:
				continue
			
			url = urlparse.urlparse(ref)
			hostname = url.hostname
			qs = urlparse.parse_qs(url.query)
			
			if not hostname: continue
			
			# Filter out known useless domains.
			if hostname in ("t.co", "longurl.org", "ow.ly", "bit.ly", "www.facebook.com", "www.weblinkvalidator.com", "static.ak.facebook.com", "info.com", "altavista.com", "tumblr.com", "www.freerepublic.com", "www.reddit.com"): continue
			if hostname.endswith(".ru"): continue
			
			# For referrals from Google, look at the 'q' argument to see how
			# people are searching for this page.
			if hostname.replace("www.", "").replace("search.", "") in ("google.com", "bing.com", "aol.com", "yahoo.com"):
				# todo, some use q= some use query=
				#print qs.get("q", [""])[0]
				continue
				
			# Filter out other domains if the link has a 'q' argument since it's probs
			# a search engine.
			if "q" in qs or "pid" in qs: continue
			
			# Filter out common paths for message boards.
			if "/threads/" in ref or "/forum/" in ref or "viewtopic.php" in ref: continue
				
			key = (m.groups(), url)
			spider[key] = spider.get(key, 0) + 1
			
		###
		
		first_print = True
		
		spider = spider.items()
		spider.sort(key = lambda kv : kv[1])
		for (bill_info, referral_url), count in spider:
			if count < min_count: continue # filter out referrers that occurred too infrequently
			
			bill_type = BillType.by_slug(bill_info[1])
			bill = Bill.objects.get(congress=bill_info[0], bill_type=bill_type, number=bill_info[2])
			
			lnk, is_new = BillLink.objects.get_or_create(
				bill=bill,
				url=referral_url.geturl(),
				defaults={
					"title": "Title Not Set"
				})
			
			# Additional processing for new entries.
			
			if not is_new: continue
			
			try:
				stream = urllib.urlopen(referral_url.geturl())
				if stream.getcode() != 200: continue
				dom = lxml.etree.parse(stream, lxml.etree.HTMLParser())
			except:
				continue
				
			title = dom.xpath('string(head/title)').strip()
			if title == "": continue
			
			# set the title of the scraped page
			lnk.title = title
			
			# white-list some domains, provided we were able to
			# get a title
			if referral_url.hostname in ("en.wikipedia.org", "www.truthorfiction.com", "www.theatlantic.com", "www.snopes.com", "arstechnica.com"):
				lnk.approved = True
			else:
				if first_print:
					print "Links pending approval:"
					print
					first_print = False
				print referral_url.geturl()
				print title.encode("utf8")
				print unicode(bill).encode("utf8")
				print
			
			lnk.save()


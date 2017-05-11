from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.contrib.auth.models import User

from optparse import make_option

from emailverification.models import BouncedEmail, Record as EVRecord

import json, urllib, urllib2

class Command(BaseCommand):
	help = 'Creates BouncedMail records for Sparkmail bounces.'
	
	def handle(self, *args, **options):
		# Process pages until there are no more results since the most recent bounce time.
		since = BouncedEmail.objects.order_by('-firstbouncetime').first().firstbouncetime.isoformat()[0:16]
		pagenum = 1
		while self.process_page(pagenum, since):
			pagenum += 1

	def process_page(self, pagenum, since):
		# Request
		url = "https://api.sparkpost.com/api/v1/message-events?" + urllib.urlencode({
			"events": "bounce",
			"bounce_classes": "10,30,90,22,23,25,50,51,52,53,54",
			"per_page": 10000, # is the max
			"from": since,
			"page": pagenum,
		})
		print(url)
		req = urllib2.Request(url)
		req.add_header("Authorization", settings.SPARKPOST_API_KEY)
		req.add_header('Content-Type', 'application/json')
		r = urllib2.urlopen(req)

		# Response
		r = json.loads(r.read())["results"]

		# Process
		for rec in r:
			self.bounce(rec["rcpt_to"], rec["reason"].replace("\n", " "))

		return len(r) > 0

	def bounce(self, email, reason):
		found = False
		
		for u in User.objects.filter(email=email):
			found = True
			print u, reason
			be, is_new = BouncedEmail.objects.get_or_create(user=u)
			if not is_new:
				be.bounces += 1
				be.save()
	
		for r in EVRecord.objects.filter(email=email):
			found = True
			print r, reason
			r.killed = True
			r.save()
			
		if not found:
			print email, "not found"

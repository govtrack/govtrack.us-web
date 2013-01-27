from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.contrib.auth.models import User

from optparse import make_option

from emailverification.models import BouncedEmail, Record as EVRecord

import sys, csv

class Command(BaseCommand):
	help = 'Creates BouncedMail records for a Dyn Email Delivery report export piped on standard input.'
	
	def handle(self, *args, **options):
		for rec in csv.DictReader(sys.stdin):
			if rec["Bounce Type"] != "hard": continue
			if rec["Bounce Rule"] != "emaildoesntexist":
				if rec["Bounce Rule"] not in ("blockedcontent", "localconfigerror", "overquota", "relayerror", "remoteconfigerror"):
					print "Unmatched rule:", rec["Bounce Rule"]
				continue
			
			found = False
			
			for u in User.objects.filter(email=rec["Emailaddress"]):
				found = True
				print u
				be, is_new = BouncedEmail.objects.get_or_create(user=u)
				if not is_new:
					be.bounces += 1
					be.save()
			
			for r in EVRecord.objects.filter(email=rec["Emailaddress"]):
				found = True
				print r
				r.killed = True
				r.save()
				
			if not found:
				print rec["Emailaddress"], "not found"


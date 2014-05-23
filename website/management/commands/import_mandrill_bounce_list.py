from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.contrib.auth.models import User

from optparse import make_option

from emailverification.models import BouncedEmail, Record as EVRecord

import sys, csv

class Command(BaseCommand):
	help = 'Creates BouncedMail records for a Mandrill delivery report export piped on standard input.'
	
	def handle(self, *args, **options):
		for rec in csv.DictReader(sys.stdin):
			email = rec["Email Address"]
			
			found = False
			
			for u in User.objects.filter(email=email):
				found = True
				print u
				be, is_new = BouncedEmail.objects.get_or_create(user=u)
				if not is_new:
					be.bounces += 1
					be.save()
			
			for r in EVRecord.objects.filter(email=email):
				found = True
				print r
				r.killed = True
				r.save()
				
			if not found:
				print email, "not found"


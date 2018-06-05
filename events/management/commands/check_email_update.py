from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from django.core.mail import send_mail, EmailMultiAlternatives
from django.template import Context, Template
from django.template.loader import get_template
from django.conf import settings

from optparse import make_option

from events.models import *
from emailverification.models import Ping, BouncedEmail

from datetime import datetime, timedelta

now = datetime.now()

class Command(BaseCommand):
	help = 'Checks the status of an email update (e.g. for when a user says they are not getting updates).'
	
	def add_arguments(self, parser):
		parser.add_argument('email_address', type=str, help="The email address or user ID.")

	def handle(self, *args, **options):
		if not options['email_address']:
			print("Specify an email address.")
			return
			
		try:
			if "@" in options['email_address']:
				user = User.objects.get(email=options['email_address'])
			else:
				user = User.objects.get(id=options['email_address'])
		except User.DoesNotExist:
			print("Not a user.")
			return
		
		print("Joined:", user.date_joined)
		print("Last Login:", user.last_login)
		
		try:
			p = Ping.objects.get(user=user)
			print("Last Ping:", p.pingtime)
		except Ping.DoesNotExist:
			print("No Ping")
			
		try:
			b = BouncedEmail.objects.get(user=user)
			print("Bounce:", b.firstbouncetime, "x" + str(b.bounces))
		except BouncedEmail.DoesNotExist:
			print("No Bounces")
			
		for sublist in user.subscription_lists.all():
			print(sublist.name, end=' ')
			if sublist.email == 0:
				print("- Emails Off")
			else:
				print("-", sublist.get_email_display(), end=' ')
				print("Last Email:", sublist.last_email_sent, end=' ')
			
				max_id, events = sublist.get_new_events()
				print(len(events), "events pending")
			
			for feed in sublist.trackers.all():
				print("\t", feed.title.encode("utf8"))

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from django.core.mail import send_mail, EmailMultiAlternatives
from django.template import Context, Template
from django.template.loader import get_template
from django.conf import settings

from optparse import make_option

from events.models import *
from website.models import UserProfile

from datetime import datetime

class Command(BaseCommand):
	help = 'Unsubscribes a user from receiving email updates.'

	def add_arguments(self, parser):
		parser.add_argument('email_address_or_id', nargs=1, type=str)
	
	def handle(self, *args, **options):
		user = options["email_address_or_id"][0]
		
		try:
			if "@" in user:
				p = UserProfile.objects.get(user__email=user)
			else:
				p = UserProfile.objects.get(user__id=user)
		except UserProfile.DoesNotExist:
			print("No such user.")
			return
		print("Turning off mass email option.")
		p.massemail = False
		p.save()
		
		print("Turning off email updates on the following subscription lists...")
		for sublist in SubscriptionList.objects.filter(user=p.user):
			print(sublist.user.email, sublist.name, "was", sublist.email)
			
			sublist.email = 0
			sublist.save()
			

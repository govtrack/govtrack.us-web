from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from django.core.mail import send_mail, EmailMultiAlternatives
from django.template import Context, Template
from django.template.loader import get_template
from django.conf import settings

from optparse import make_option

from events.models import *

from datetime import datetime

class Command(BaseCommand):
	args = 'user@email.com'
	help = 'Unsubscribes a user from receiving email updates.'
	
	def handle(self, *args, **options):
		if len(args) != 1:
			print "Specify a user's email address."
			return
		
		print "Turning off email updates on the following subscription lists..."
		for sublist in SubscriptionList.objects.filter(user__email=args[0]):
			print sublist.user.email, sublist.name, sublist.email
			
			sublist.email = 0
			sublist.save()
			

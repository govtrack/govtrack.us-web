from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from django.core.mail import send_mail, EmailMultiAlternatives
from django.template import Context, Template
from django.template.loader import get_template
from django.conf import settings

from optparse import make_option

from events.models import *
from website.models import UserProfile

import sys
from datetime import datetime

class Command(BaseCommand):
	help = 'Unsubscribes user listed on STDIN from receiving email updates.'

	def handle(self, *args, **options):
		for line in sys.stdin:
			if line.strip():
				self.unsubscribe(line.strip())

	def unsubscribe(self, user):
		try:
			if "@" in user:
				p = UserProfile.objects.get(user__email=user)
			else:
				p = UserProfile.objects.get(user__id=user)
		except UserProfile.DoesNotExist:
			print(user, "no such user")
			return

		p.one_click_unsub_hit = datetime.now()
		p.massemail = False
		p.save()
		SubscriptionList.objects.filter(user=p.user).update(email=0)
		print(user)

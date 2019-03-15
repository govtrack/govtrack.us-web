from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone
import django.core.mail

from datetime import timedelta

from website.models import UserProfile
from events.models import SubscriptionList
from emailverification.models import Ping
from htmlemailer import send_mail

now = timezone.now()

class Command(BaseCommand):
	help = 'Sends long-term inactive users a warning that they will stop getting email updates.'

	def handle(self, *args, **options):
		with django.core.mail.get_connection() as mail_connection:
			self.scan_users(mail_connection)

	def scan_users(self, mail_connection):
		# Find users who haven't logged in in 3 years and still have
		# email updates turned on.
		qs = UserProfile.objects.filter(
			user__last_login__lt=now-timedelta(days=365*3),
			user__subscription_lists__email__gt=0
		).distinct()
		for userprof in qs.select_related('user'):
			# * Are not already inactive.
			if userprof.is_inactive(): continue

			# * They haven't hit the hidden image ping URL in the last six months by opening an email update.
			if Ping.objects.filter(user=userprof.user, pingtime__gt=now-timedelta(days=30.5*6)).exists(): continue

			# If they haven't received an email from us in the last 2.5 years (i.e. at least a whole Congress)
			# then just inactivate the user immediately so that we can stop checking if they have updates.
			if SubscriptionList.objects.filter(user=userprof.user, last_email_sent__gt=now-timedelta(days=365*2.5)).exists():
				self.send_warning(userprof.user, mail_connection)

			userprof.inactivity_warning_sent = now
			userprof.save()
			print(userprof.user.id, userprof.user.date_joined, userprof.user.email)

	def send_warning(self, user, mail_connection):
		emailfromaddr = settings.EMAIL_UPDATES_FROMADDR
		emailreturnpath = settings.EMAIL_UPDATES_RETURN_PATH % user.id
		send_mail(
            "email/inactivity_warning",
            emailreturnpath,
            [user.email],
            {
                "user": user,
				"last_email": SubscriptionList.objects.filter(user=user).order_by('-last_email_sent').first().last_email_sent,
            },
            headers={
                'Reply-To': emailfromaddr,
                'Auto-Submitted': 'auto-generated',
                'X-Auto-Response-Suppress': 'OOF',
            },
			connection=mail_connection
        )

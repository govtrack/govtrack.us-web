from django.core.management.base import BaseCommand, CommandError

from django.db.models import F
from django.conf import settings

from django.contrib.auth.models import User
from website.models import UserProfile
from emailverification.models import BouncedEmail
from htmlemailer import send_mail

from datetime import datetime, timedelta

blast_id = 2

class Command(BaseCommand):
	args = 'test|go'
	help = 'Sends out an email blast to users with a site announcement.'
	
	def handle(self, *args, **options):
		# Definitions for the four groups of users.

		if args[0] not in ("go", "count"):
			# test email
			users = UserProfile.objects.filter(user__id__in=(5,)) # me and Ben  353071
		else:
			# Users who have subscribed to email updates and received one
			# recently but did not join too recently.
			users = UserProfile.objects.filter(
				user__subscription_lists__email__gt=0,
				user__subscription_lists__last_email_sent__gt=datetime.now()-timedelta(days=31*1),
				user__date_joined__lt=datetime.now()-timedelta(days=31*12),
				user__last_login__gt=F('user__date_joined'),
				).distinct()

			# also require:
			# * the mass email flag is turned
			# * we haven't sent them this blast already
			users = users.filter(
					massemail=True,
					last_mass_email__lt=blast_id,
					)

		print users.count()
			
		if args[0] == "count":
			return
		if args[0] not in ("go", "test"): raise Exception("sanity check fail")

		# Get the list of user IDs.
			
		users = list(users.order_by("user__id").values_list("user", flat=True))
		
		print "Sending..."
			
		total_emails_sent = 0
		for userid in users:
			if send_blast(userid, args[0] == "test"):
				total_emails_sent += 1
			
			from django import db
			db.reset_queries()
			
		print "sent", total_emails_sent, "emails"

def send_blast(user_id, is_test):
	user = User.objects.get(id=user_id)
	prof = user.userprofile()

	# from address / return path address
	emailfromaddr = getattr(settings, 'EMAIL_UPDATES_FROMADDR',
			getattr(settings, 'SERVER_EMAIL', 'no.reply@example.com'))
	emailreturnpath = emailfromaddr
	if hasattr(settings, 'EMAIL_UPDATES_RETURN_PATH'):
		emailreturnpath = (settings.EMAIL_UPDATES_RETURN_PATH % user.id)
	
	# send!
	try:
		print "emailing", user.id, user.email
		send_mail(
			"website/email/blast",
			emailreturnpath,
			[user.email],
			{
			},
			headers = {
				'From': emailfromaddr,
				'X-Auto-Response-Suppress': 'OOF',
			},
			fail_silently=False
		)
	except Exception as e:
		print user, e
		return False
	
	if not is_test:
		prof.last_mass_email = blast_id
		prof.save()
		
	return True # success


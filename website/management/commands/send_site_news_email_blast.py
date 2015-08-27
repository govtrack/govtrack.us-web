from django.core.management.base import BaseCommand, CommandError

from django.db.models import F
from django.conf import settings

from django.contrib.auth.models import User
from website.models import UserProfile
from emailverification.models import BouncedEmail
from htmlemailer import send_mail

from datetime import datetime, timedelta

blast_id = 3

class Command(BaseCommand):
	args = 'test|go'
	help = 'Sends out an email blast to users with a site announcement.'
	
	def handle(self, *args, **options):
		# Definitions for the four groups of users.

		if args[0] not in ("go", "count"):
			# test email
			users = UserProfile.objects.filter(user__id__in=(5,)) # me
			test_addrs = args[1:]
		else:
			# Users who have subscribed to email updates and received one recently-ish....
			users = UserProfile.objects.filter(
				user__subscription_lists__email__gt=0,
				user__last_login__lt=datetime.now()-timedelta(days=365*2),
				#user__subscription_lists__last_email_sent__gt=datetime.now()-timedelta(days=31*12),
				#user__date_joined__lt=datetime.now()-timedelta(days=14),
				#user__last_login__gt=F('user__date_joined'),
				).distinct()

			# also require:
			# * the mass email flag is turned
			# * we haven't sent them this blast already
			users = users.filter(
					massemail=True,
					last_mass_email__lt=blast_id,
					)

			test_addrs = None

		print users.count(), test_addrs
			
		if args[0] == "count":
			return
		if args[0] not in ("go", "test"): raise Exception("sanity check fail")

		# Get the list of user IDs.
			
		users = list(users.order_by("user__id").values_list("user", flat=True))

		# For multi-processing, we have to close the database connection betfore
		# workers are spawned.
		from django.db import connection 
		connection.close()
		
		print "Sending..."
			
		# When we send a lot, each one goes slowly. Use a Pool
		# to submit the mail jobs in parallel. Only submit a
		# batch at a time - wait for each batch to complete
		# before continuing because I'm not sure how to do it
		# reasonably otherwise.

		from multiprocessing import Pool

		# make state variables that local function can see
		class State: pass
		State = State()
		State.total_emails_sent = 0
		State.workers = []

		def wait_workers():
			for ar in State.workers:
				if ar.get():
					State.total_emails_sent += 1
			State.workers = []

		pool = Pool(processes=3)

		for i, userid in enumerate(users):
			#if send_blast(userid, args[0] == "test", test_addrs, i, len(users)):
			#	total_emails_sent += 1
			ar = pool.apply_async(
				send_blast,
				[userid, args[0] == "test", test_addrs, i, len(users)])
			State.workers.append(ar)
				
			if len(State.workers) > 15:
				wait_workers()

				# if DEBUG, clear memory
				from django import db
				db.reset_queries()

		wait_workers()
			
		print "sent", State.total_emails_sent, "emails"

def send_blast(user_id, is_test, test_addrs, counter, counter_max):
	user = User.objects.get(id=user_id)
	prof = user.userprofile()

	# skip users that have had a bounced email recorded - avoid getting bad reputation
	if BouncedEmail.objects.filter(user=user).exists():
		return

	# from address / return path address
	emailfromaddr = getattr(settings, 'EMAIL_UPDATES_FROMADDR',
			getattr(settings, 'SERVER_EMAIL', 'no.reply@example.com'))
	emailreturnpath = emailfromaddr
	if hasattr(settings, 'EMAIL_UPDATES_RETURN_PATH'):
		emailreturnpath = (settings.EMAIL_UPDATES_RETURN_PATH % user.id)

	# to: address
	send_to_addr = [user.email]
	if is_test and test_addrs: send_to_addr = test_addrs
	
	# send!
	try:
		print "%d/%d" % (counter+1, counter_max), user.id, ", ".join(send_to_addr)
		send_mail(
			"website/email/blast",
			emailreturnpath,
			send_to_addr,
			{
				"unsub_url": settings.SITE_ROOT_URL + "/accounts/unsubscribe/" + prof.get_one_click_unsub_key()
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


from django.core.management.base import BaseCommand, CommandError

from django.db.models import F, Q
from django.conf import settings

from django.contrib.auth.models import User
from website.models import UserProfile
from emailverification.models import BouncedEmail
from htmlemailer import send_mail

from datetime import datetime, timedelta

blast_id = 8

class Command(BaseCommand):
	help = 'Sends out an email blast to users with a site announcement.'

	def add_arguments(self, parser):
		parser.add_argument('go', nargs=1, type=str)

	def handle(self, *args, **options):
		cmd = options["go"][0]
		if cmd not in ("go", "count"):
			# test email
			users = UserProfile.objects.filter(user__id__in=(5,)) # me
			test_addrs = [cmd]
		else:
			# some subset of users
			users = UserProfile.objects.all()#\
				#.filter(
				#    Q(user__subscription_lists__last_email_sent__gt=datetime.now()-timedelta(days=31*12))
				#  | Q(user__last_login__gt=datetime.now()-timedelta(days=31*12))
				#  | Q(user__date_joined__gt=datetime.now()-timedelta(days=31*12))
				#  | Q(last_blog_post_emailed__gt=0)
                #).distinct()

			# also require:
			# * the mass email flag is not turnd off
			# * we haven't sent them this blast already
			users = users.filter(
					massemail=True,
					last_mass_email__lt=blast_id,
					)

			test_addrs = None

		# Get the list of user IDs.
		users = set(users.values_list("user", flat=True))

		# Skip users that have had a bounced email recorded - avoid getting bad reputation
		bounced = set(BouncedEmail.objects.order_by("user__id").values_list("user", flat=True))
		users = users - bounced
		users = list(users)

		print(len(users), test_addrs)
		if cmd == "count":
			return

		# Only do a batch.

		batch_size = 50000
		if len(users) > batch_size:
			import random
			users = random.sample(users, batch_size)

		# For multi-processing, we have to close the database connection betfore
		# workers are spawned.
		from django.db import connection 
		connection.close()
		
		print("Sending...")
			
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

		def wait_workers(n):
			# Wait for any of the workers to complete until
			# there are not more than N workers.
			while len(State.workers) > n:
				timeout = .1 / len(State.workers) # pause a bit for each worker to complete
				for ar in State.workers:
					#print(len(State.workers), "|", ar, timeout, "...")
					ar.wait(timeout)
					if ar.ready():
						#print("   popped")
						State.total_emails_sent += 1
						State.workers.remove(ar)
						break

		pool = Pool(processes=3)

		for i, userid in enumerate(users):
			ar = pool.apply_async(
				send_blast,
				[userid, cmd != "go", test_addrs, i, len(users)])
			State.workers.append(ar)
				
			if wait_workers(8):
				# if DEBUG, clear memory
				from django import db
				db.reset_queries()

		wait_workers(0)
			
		print("sent", State.total_emails_sent, "emails")

def send_blast(user_id, is_test, test_addrs, counter, counter_max):
	user = User.objects.get(id=user_id)
	prof = user.userprofile()

	# from address / return path address
	emailfromaddr = getattr(settings, 'SERVER_EMAIL', 'no.reply@example.com')
	emailreturnpath = emailfromaddr
	if hasattr(settings, 'EMAIL_UPDATES_RETURN_PATH'):
		emailreturnpath = (settings.EMAIL_UPDATES_RETURN_PATH % user.id)

	# to: address
	send_to_addr = [user.email]
	if is_test and test_addrs: send_to_addr = test_addrs
	
	# send!
	try:
		print("%d/%d" % (counter+1, counter_max), user.id, ", ".join(send_to_addr))
		send_mail(
			"website/email/blast",
			emailreturnpath,
			send_to_addr,
			{
				"unsub_url": settings.SITE_ROOT_URL + "/accounts/unsubscribe/" + prof.get_one_click_unsub_key()
			},
			headers = {
				'From': settings.SERVER_EMAIL,
				#'Reply-To': "GovTrack.us <hello@govtrack.us>",
				'Auto-Submitted': 'auto-generated',
				'X-Auto-Response-Suppress': 'OOF',
				'X-Unsubscribe-Link': prof.get_one_click_unsub_url(),
				'List-Unsubscribe': "<" + prof.get_one_click_unsub_url() + ">",
			},
			fail_silently=False
		)
	except Exception as e:
		print(user, e)
		return False
	
	if not is_test:
		prof.last_mass_email = blast_id
		prof.save()
		
	return True # success


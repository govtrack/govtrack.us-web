import django
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.template import Context, Template
from django.template.loader import get_template
from django.conf import settings
import django.core.mail

from optparse import make_option

from website.models import UserProfile
from events.models import *
from emailverification.models import Ping, BouncedEmail
from htmlemailer import send_mail as send_html_mail

import os, sys
from datetime import datetime, timedelta
import yaml
from website.templatetags.govtrack_utils import markdown

launch_time = datetime.now()

import multiprocessing
django.setup() # StackOverflow user says call setup when using multiprocessing

# globals that are loaded by the parent process before forking children
announce = None
medium_posts = None

class Command(BaseCommand):
	help = 'Sends out email updates of events to subscribing users.'

	def add_arguments(self, parser):
		parser.add_argument('mode', nargs=1, type=str)
	
	def handle(self, *args, **options):
		global announce
		global medium_posts

		if options["mode"][0] not in ('daily', 'weekly', 'testadmin', 'testcount'):
			print("Specify daily or weekly or testadmin or testcount.")
			return

		if options["mode"][0] == "testadmin":
			# Test an email to the site administrator only. There's no need to be complicated
			# about finding users --- just use a hard-coded list.
			users = User.objects.filter(email="tauberer@govtrack.us")
			send_mail = True
			mark_lists = False
			send_old_events = True
			list_email_freq = (1,2)
		else:
			# Now that the number of registered users is much larger than the number of event-generating
			# feeds, it is faster to find users to update by starting with the most recent events.
			
			users = None
			send_mail = True
			mark_lists = True
			send_old_events = False
			if options["mode"][0] == "daily":
				list_email_freq = (1,)
				back_days = BACKFILL_DAYS_DAILY
			elif options["mode"][0] == "weekly":
				list_email_freq = (1,2)
				back_days = BACKFILL_DAYS_WEEKLY
			elif options["mode"][0] == "testcount":
				# count up how many daily emails we would send, but don't send any
				list_email_freq = (1,)
				send_mail = False
				mark_lists = False
				back_days = BACKFILL_DAYS_DAILY

			# Find the subscription lists w/ emails turned on.
			# Exclude lists we sent an email out to in the last 20 hours, in case we're
			# re-starting this process and some new events crept in.
			sublists = SubscriptionList.objects\
					.filter(email__in=list_email_freq)\
					.exclude(last_email_sent__gt=launch_time-timedelta(hours=20))

			# And get a list of those users.
			users = User.objects.filter(subscription_lists__in=sublists).distinct()

		if os.environ.get("START"):
			users = users.filter(id__gte=int(os.environ["START"]))
				#, id__lt=169660)

		users = users\
				.values("id", "email", "last_login")\
				.order_by('id')

		# enable caching during event generation
		enable_event_source_caching()

		# load general announcement
		announce = load_announcement("website/email/email_update_announcement.md", options["mode"][0] == "testadmin")

		# get GovTrack Insider posts
		from website.models import MediumPost
		medium_posts = MediumPost.objects.order_by('-published')[0:6]

		# counters for analytics on what we sent
		counts = {
			"total_emails_sent": 0,
			"total_events_sent": 0,
			"total_users_skipped_stale": 0,
			"total_users_skipped_bounced": 0,
			"total_time_querying": timedelta(seconds=0),
			"total_time_rendering": timedelta(seconds=0),
			"total_time_sending": timedelta(seconds=0),
		}

		# when debugging, show a progress meter
		def user_iterator(): return users
		if sys.stdout.isatty(): 
			def user_iterator():
				import tqdm
				return tqdm.tqdm(list(users))

		# Create a pool of workers. (multiprocessing.Pool behaves weirdly with Django.)
		# Sparkpost says have up to 10 concurrent connections.
		for db in django.db.connections.all(): db.close() # close before forking
		def create_worker():
			parent_conn, child_conn = multiprocessing.Pipe()
			proc = multiprocessing.Process(target=pool_worker, args=(child_conn,))
			proc.start()
			return [proc, parent_conn, 0]
		pool = [create_worker() for i in range(5)]

		def dequeue(worker, limit):
			while worker[2] > limit:
				wcounts = worker[1].recv()
				worker[2] -= 1
				for k, v in wcounts.items():
					counts[k] += v

		for i, user in enumerate(user_iterator()):
            # Skip users who have been given an inactivity warning and have not
            # logged in afterwards.
			if UserProfile.objects.get(user_id=user["id"]).is_inactive():
				counts["total_users_skipped_stale"] += 1
				continue

            # Skip users that emails to whom have bounced.
			if BouncedEmail.objects.filter(user_id=user["id"]).exists():
				counts["total_users_skipped_bounced"] += 1
				continue

			# if debugging, can run it in the main process and ignore the pool
			#wcounts = send_email_update(user["id"], list_email_freq, send_mail, mark_lists, send_old_events)
			#for k, v in wcounts.items(): counts[k] += v
			#continue

			# Enque task.
			worker = pool[i % len(pool)]
			worker[1].send([user["id"], list_email_freq, send_mail, mark_lists, send_old_events])
			worker[2] += 1

			# Deque results periodically so that the loop tracks overall progress and the pipe doesn't hit a limit.
			dequeue(worker, 10)

		# signal we're done so processes terminate
		for worker in pool: worker[1].send(None)

		# join
		for worker in pool: dequeue(worker, 0)
		for worker in pool: worker[0].join(1)

		# show stats
		print("Sent" if send_mail else "Would send", counts["total_emails_sent"], "emails and", counts["total_events_sent"], "events")
		for k, v in list(counts.items()):
			print(k, v)

		# show queries (requires DEBUG to be true)
		if settings.DEBUG:
			from django.db import connection
			for q in connection.queries:
				if float(q["time"]) > 0:
					print(q["time"], q["sql"])

def pool_worker(conn):
	try:
		# close db connections in forked children on start
		# in case there was any shared state with parent process
		for db in django.db.connections.all(): db.close()

		# open a new email connection
		with django.core.mail.get_connection() as mail_connection:
		
			# Process incoming tasks.
			while True:
				args = conn.recv()
				if args is None: break # stop when we get a None
				conn.send(send_email_update(*args, mail_connection=mail_connection))

			# Close the connection.
			conn.close()
	except Exception as e:
		print("Uncaught exception", e)

def send_email_update(user_id, list_email_freq, send_mail, mark_lists, send_old_events, mail_connection=None):
	global launch_time

	user_start_time = datetime.now()

	user = User.objects.get(id=user_id)
	
	# get the email's From: header and return path
	emailfromaddr = getattr(settings, 'EMAIL_UPDATES_FROMADDR',
			getattr(settings, 'SERVER_EMAIL', 'no.reply@example.com'))
	emailreturnpath = emailfromaddr
	if hasattr(settings, 'EMAIL_UPDATES_RETURN_PATH'):
		emailreturnpath = (settings.EMAIL_UPDATES_RETURN_PATH % user.id)

	# Process each of the subscription lists.
	all_trackers = set()
	eventslists = []
	most_recent_event = None
	eventcount = 0
	for sublist in user.subscription_lists.all():
		# Get a list of all of the trackers this user has in all lists. We use the
		# complete list, even in non-email-update-lists, for rendering events.
		all_trackers |= set(sublist.trackers.all())

		# If this list does not have email updates turned on, move on.
		if sublist.email not in list_email_freq: continue

		# For debugging, clear the last_event_mailed flag so we can find some events
		# to send.
		if send_old_events: sublist.last_event_mailed = None

		# Get any new events to email the user about.
		max_id, events = sublist.get_new_events()
		if len(events) > 0:
			eventslists.append( (sublist, events) )
			eventcount += len(events)
			if most_recent_event is None: most_recent_event = max_id
			most_recent_event = max(most_recent_event, max_id)

	user_querying_end_time = datetime.now()
	
	# Don't send an empty email.... unless we're testing and we want to send some old events.
	if len(eventslists) == 0 and not send_old_events and announce is None:
		return {
			"total_time_querying": user_querying_end_time-user_start_time,
		}


	# When counting what we want to send, we supress emails.
	if not send_mail:
		# don't email, don't update lists with the last emailed id
		return {
			"total_events_sent": eventcount,
			"total_time_querying": user_querying_end_time-user_start_time,
		}
	
	# Add a pingback image into the email to know (with some low accuracy) which
	# email addresses are still valid, for folks that have not logged in recently
	# and did not successfully recently ping back.
	emailpingurl = None
	if user.last_login < launch_time - timedelta(days=60) \
		and not Ping.objects.filter(user=user, pingtime__gt=launch_time - timedelta(days=60)).exists():
		emailpingurl = Ping.get_ping_url(user)

	# ensure smtp connection is open in case it got shut (hmm)
	if mail_connection.connection and not mail_connection.connection.sock: mail_connection.connection = None
	mail_connection.open()
		
	# send
	try:
		timings = { }
		send_html_mail(
			"events/emailupdate",
			emailreturnpath,
			[user.email],
			{
				"user": user,
				"date": datetime.now().strftime("%b. %d").replace(" 0", " "),
				"eventslists": eventslists,
				"feed": all_trackers, # use all trackers in the user's account as context for displaying events
				"emailpingurl": emailpingurl,
				"SITE_ROOT_URL": settings.SITE_ROOT_URL,
				"announcement": announce,
				"medium_posts": medium_posts,
			},
			headers={
				'Reply-To': emailfromaddr,
				'Auto-Submitted': 'auto-generated',
				'X-Auto-Response-Suppress': 'OOF',
			},
			fail_silently=False,
			connection=mail_connection,
			#timings=timings
		)
	except Exception as e:
		if "recipient address was suppressed due to" in str(e):
			be, is_new = BouncedEmail.objects.get_or_create(user=user)
			if not is_new:
				be.bounces += 1
				be.save()
			print(user, "user is on suppression list already")
		else:
			print(user, e)
		# raise - debugging - must also disable process pool to see what happened

		# don't update this user's lists with what events were sent because it failed
		return {
			"total_time_querying": user_querying_end_time-user_start_time,
			"total_time_sending": datetime.now()-user_querying_end_time,
		}
	
	if mark_lists: # skipped when debugging
		# mark each list as having mailed events up to the max id found from the
		# events table so that we know not to email those events in a future update.
		for sublist, events in eventslists:
			sublist.last_event_mailed = max(sublist.last_event_mailed, most_recent_event) if sublist.last_event_mailed is not None else most_recent_event
			sublist.last_email_sent = launch_time
			sublist.save()

	return {
		"total_emails_sent": 1,
		"total_events_sent": eventcount,
		"total_time_querying": user_querying_end_time-user_start_time,
		#"total_time_rendering": timings["render"],
		#"total_time_sending": timings["send"],
	}

def load_announcement(template_path, testing):
	# Load the Markdown template for the current blast.
	templ = get_template(template_path)

	# Get the text-only body content, which also includes some email metadata.
	# Replace Markdown-style [text][href] links with the text plus bracketed href.
	ctx = { "format": "text", "utm": "" }
	body_text = templ.render(ctx).strip()
	body_text = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1 at \2", body_text)

	# The top of the text content contains metadata in YAML format,
	# with "id" and "subject" required and active: true or rundate set to today's date in ISO format.
	meta_info, body_text = body_text.split("----------", 1)
	body_text = body_text.strip()
	meta_info = yaml.load(meta_info)

	# Under what cases do we use this announcement?
	if meta_info.get("active"):
		pass # active is set to something truthy
	elif meta_info.get("rundate") == launch_time.date().isoformat():
		pass # rundate matches date this job was started
	elif "rundate" in meta_info and testing:
		pass # when testing ignore the actual date set
	else:
		# the announcement file is inactive/stale
		return None

	# Get the HTML body content.
	ctx = {
		"format": "html",
		"utm": "",
	}
	body_html = templ.render(ctx).strip()
	body_html = markdown(body_html)

	# Store everything in meta_info.
	
	meta_info["body_text"] = body_text
	meta_info["body_html"] = body_html
	
	return meta_info



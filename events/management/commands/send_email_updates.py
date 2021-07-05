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

# If this command takes longer than it should, we could end up starting the next
# day's process before this one finishes. There's nothing strictly wrong with
# that, but we don't want to put so much load on the server, and it should be
# an error condition for the process to run for so long.
from exclusiveprocess import Lock
Lock(die=True).forever()

launch_time = datetime.now()

import multiprocessing
django.setup() # StackOverflow user says call setup when using multiprocessing

#if debugging single-threade
#global_mail_connection = django.core.mail.get_connection()
#global_mail_connection.open()

# globals that are loaded by the parent process before forking children
utm = "utm_campaign=govtrack_email_update&utm_source=govtrack/email_update&utm_medium=email"
template_body_text = None
template_body_html = None
announce = None
medium_posts = None

class Command(BaseCommand):
	help = 'Sends out email updates of events to subscribing users.'

	def add_arguments(self, parser):
		parser.add_argument('mode', nargs=1, type=str)
	
	def handle(self, *args, **options):
		global template_body_text
		global template_body_html
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
			# Find the subscription lists w/ daily emails turned on.
			# Exclude lists we sent an email out to in the last 20 hours,
			# in case we're re-starting this process and some new events crept in.
			sublists = SubscriptionList.objects\
				.filter(email=1)\
				.exclude(last_email_sent__gt=launch_time-timedelta(hours=20))
			
			users = None
			send_mail = True
			mark_lists = True
			send_old_events = False
			if options["mode"][0] == "daily":
				list_email_freq = (1,)
			elif options["mode"][0] == "weekly":
				list_email_freq = (1,2)
				# Add in the subscription lists for weekly updates (we do both daily and weekly when
				# we run the weekly batch) but in case we're re-starting the batch, don't send emails
				# to users if they only have a weekly list and we emailed them during the week.
				sublists |= SubscriptionList.objects\
					.filter(email=2)\
					.exclude(last_email_sent__gt=launch_time-timedelta(days=5))
			elif options["mode"][0] == "testcount":
				# count up how many daily emails we would send, but don't send any
				list_email_freq = (1,)
				send_mail = False
				mark_lists = False

			# And get a list of those users.
			users = User.objects.filter(subscription_lists__in=sublists).distinct()

		if os.environ.get("START"):
			users = users.filter(id__gte=int(os.environ["START"]))
				#, id__lt=169660)

		users = users\
				.filter(is_active=True)\
				.values("id", "email", "last_login")\
				.order_by('id')

		# enable caching during event generation
		enable_event_source_caching()

		# load globals
		template_body_text = get_template("events/emailupdate_body.txt")
		template_body_html = get_template("events/emailupdate_body.html")
		announce = load_announcement("website/email/email_update_announcement.md", options["mode"][0] == "testadmin")

		# get GovTrack Insider posts
		from website.models import MediumPost
		medium_posts = list(MediumPost.objects.order_by('-published')[0:6])

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
		def create_worker():
			for db in django.db.connections.all(): db.close() # close before forking
			parent_conn, child_conn = multiprocessing.Pipe()
			proc = multiprocessing.Process(target=pool_worker, args=(child_conn,))
			proc.start()
			return [proc, parent_conn, 0]
		pool = [create_worker() for i in range(5)]
		
		def dequeue(worker, limit):
			while worker[2] > limit: # the worker has more than limit emails in its queue
				# Each worker sends back some data each time it finishes handling
				# a user's email updates. Get that data and aggregate it.
				# But our workers get stuck, so poll for a bit waiting for the
				# email to send. If it doesn't finish, abort the worker.
				try:
					if not worker[1].poll(60*10): # 10 minutes
						raise ConnectionResetError()
					wcounts = worker[1].recv()
					worker[2] -= 1
					for k, v in wcounts.items():
						counts[k] += v
				except ConnectionResetError:
					# Worker seems to be stuck or gone.
					print("Worker got stuck/died. Making a new one.")
					worker[1].close()
					worker[0].terminate()
					return create_worker()
			return worker

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

			## if debugging, can run it in the main process and ignore the pool
			#wcounts = send_email_update(user["id"], list_email_freq, send_mail, mark_lists, send_old_events, global_mail_connection)
			#for k, v in wcounts.items(): counts[k] += v

			# Enque task.
			while True:
				worker = pool[i % len(pool)]
				try:
					worker[1].send([user["id"], list_email_freq, send_mail, mark_lists, send_old_events])
					worker[2] += 1
					break
				except BrokenPipeError:
					# Something is wrong with the worker. Kill it and make
					# a new worker, and then try again.
					print("Worker pipe broken. Making a new one.")
					worker[1].close()
					worker[0].terminate()
					pool[i % len(pool)] = create_worker()
					continue

			# Deque results periodically so that the loop tracks overall progress and the pipe doesn't hit a limit.
			# If a worker gets stuck, replace it with a new one.
			pool[i % len(pool)] = dequeue(worker, 10)

		# signal we're done so processes terminate, then join to reclaim the workers
		for worker in pool: worker[1].send(None)
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
				conn.send(send_email_update(*args, mail_connection))

			# Close the connection.
			conn.close()
	except Exception as e:
		print("Uncaught exception", e)

def send_email_update(user_id, list_email_freq, send_mail, mark_lists, send_old_events, mail_connection):
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

	# Render the body of the email.
	body_context = {
		"eventslists": eventslists,
		"feed": all_trackers, # use all trackers in the user's account as context for displaying events
		"SITE_ROOT_URL": settings.SITE_ROOT_URL,
		"utm": utm,
	}
	body_text = template_body_text.render(context=body_context)
	body_html = template_body_html.render(context=body_context)
	user_rendering_end_time = datetime.now()

	# When counting what we want to send, we supress emails.
	if not send_mail:
		# don't email, don't update lists with the last emailed id
		return {
			"total_events_sent": eventcount,
			"total_time_querying": user_querying_end_time-user_start_time,
			"total_time_rendering": user_rendering_end_time-user_querying_end_time,
		}
	
	# Add a pingback image into the email to know (with some low accuracy) which
	# email addresses are still valid, for folks that have not logged in recently
	# and did not successfully recently ping back.
	emailpingurl = None
	if user.last_login < launch_time - timedelta(days=60) \
		and not Ping.objects.filter(user=user, pingtime__gt=launch_time - timedelta(days=60)).exists():
		emailpingurl = Ping.get_ping_url(user)

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
				"emailpingurl": emailpingurl,
				"body_text": body_text,
				"body_html": body_html,
				"announcement": announce,
				"medium_posts": medium_posts,
				"SITE_ROOT_URL": settings.SITE_ROOT_URL,
				"utm": utm,
			},
			headers={
				'Reply-To': emailfromaddr,
				'Auto-Submitted': 'auto-generated',
				'X-Auto-Response-Suppress': 'OOF',
				'X-Unsubscribe-Link': UserProfile.objects.get(user=user).get_one_click_unsub_url(),
			},
			fail_silently=False,
			connection=mail_connection,
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

	user_sending_end_time = datetime.now()

	return {
		"total_emails_sent": 1,
		"total_events_sent": eventcount,
		"total_time_querying": user_querying_end_time-user_start_time,
		"total_time_rendering": user_rendering_end_time-user_querying_end_time,
		"total_time_sending": user_sending_end_time-user_rendering_end_time,
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



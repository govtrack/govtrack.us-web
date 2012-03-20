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
	args = 'daily|weekly|testadmin|testcount'
	help = 'Sends out email updates of events to subscribing users.'
	
	def handle(self, *args, **options):
		if len(args) != 1:
			print "Specify daily or weekly or testadmin or testcount."
			return
		if args[0] not in ('daily', 'weekly', 'testadmin', 'testcount'):
			print "Specify daily or weekly or testadmin or testcount."
			return
		
		# What kind of subscription lists are we processing?
		users = None
		testing = False
		if args[0] == "daily":
			list_email_freq = (1,)
		elif args[0] == "weekly":
			list_email_freq = (1,2)
		elif args[0] == "testadmin":
			# test an email to the site administrator only
			list_email_freq = (1,2)
			users = User.objects.filter(email="jt@occams.info")
		elif args[0] == "testcount":
			# count up how many daily emails we would send, but don't send any
			list_email_freq = (1,)
			testing = True

		if users == None: # overridden for the testadmin case
			# Find all users who have a subscription list with email
			# updates turned on to the right daily/weekly setting.
			users = User.objects.filter(subscription_lists__email__in = list_email_freq).distinct()

		total_emails_sent = 0
		total_events_sent = 0
		for user in list(users.order_by('id')): # clone up front to avoid holding the cursor (?)
			events_sent = send_email_update(user, list_email_freq, testing)
			if events_sent > 0:
				total_emails_sent += 1
				total_events_sent += events_sent
			
			#from django.db import connection
			#for q in connection.queries:
			#	print q["time"], q["sql"]
			from django import db
			db.reset_queries()
				
		print "Sent" if not testing else "Would send", total_emails_sent, "emails and", total_events_sent, "events"
			
def send_email_update(user, list_email_freq, testing):
	emailfromaddr = getattr(settings, 'EMAIL_UPDATES_FROMADDR',
			getattr(settings, 'SERVER_EMAIL', 'no.reply@example.com'))
		
	emailsubject = "GovTrack.us Email Update for %s" % datetime.now().strftime("%x")

	all_trackers = set()

	eventslists = []
	most_recent_event = None
	eventcount = 0
	for sublist in user.subscription_lists.all():
		all_trackers |= set(sublist.trackers.all()) # include trackers for non-email-update list
		if sublist.email in list_email_freq:
			events = sublist.get_new_events()
			if len(events) > 0:
				eventslists.append( (sublist, events) )
				eventcount += len(events)
				for evt in events:
					most_recent_event = max(most_recent_event, evt["id"])
	
	if len(eventslists) == 0:
		return 0
		
	if testing:
		# don't email, don't update lists with the last emailed id
		return len(events)
		
	templ_txt = get_template("events/emailupdate.txt")
	templ_html = get_template("events/emailupdate.html")
	ctx = Context({
		"eventslists": eventslists,
		"feed": all_trackers, # use all trackers in the user's account as context for displaying events
	})
	
	email = EmailMultiAlternatives(emailsubject, templ_txt.render(ctx), emailfromaddr, [user.email])
	email.attach_alternative(templ_html.render(ctx), "text/html")
	
	try:
		print "emailing", user.id, user.email, "x", eventcount, "..."
		email.send(fail_silently=False)
	except IOError as e:
		print user, e
		return 0 # skip updating what events were sent, False = did not sent
	
	# mark each list as having mailed events up to the max id found from the
	# events table so that we know not to email those events in a future update.
	for sublist, events in eventslists:
		sublist.last_event_mailed = max(sublist.last_event_mailed, most_recent_event)
		sublist.save()
		
	return eventcount # did sent email

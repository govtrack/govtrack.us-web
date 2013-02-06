from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from django.conf import settings

from optparse import make_option

from events.models import SubscriptionList
from emailverification.utils import send_email_verification

from datetime import datetime, timedelta

class Command(BaseCommand):
	args = '[test|send]'
	help = 'Warn users that have not logged in recently that their email updates will be turned off.'
	
	def handle(self, *args, **options):
		cutoff = (datetime.now()-timedelta(days=365*3)).date().replace(day=1)
		users = SubscriptionList.objects\
			.filter(email__gt=0, user__last_login__lt=cutoff)\
			.exclude(user__ping__pingtime__isnull=False)\
			.values_list("user", "user__email", "user__last_login").distinct()
		
		print "Cutoff:", cutoff.isoformat()
		print "Lists:", users.count()
		print "Emailed since 2.0:", users.exclude(last_event_mailed=None).count()

		if len(args) > 0 and args[0] == "send":
			for user in users:
				axn = UserAction()
				axn.uid = user[0]
				print user
				send_email_verification(user[1], None, axn)

class UserAction:
	uid = None
	
	def email_subject(self):
		return "Your GovTrack.us Email Updates May Be Turned Off"
	
	def email_body(self):
		return """Are you still interested in getting email updates from www.GovTrack.us?
		
You registered more than three years ago to get updates by email about what is happening in Congress, but we haven't heard from you in a while. We're cleaning house as we improve GovTrack. Your email updates will be turned off if you do not log in to GovTrack within the next two weeks.

To continue your email updates, just follow this link:

<URL>

Thank you for your interest in GovTrack.

www.govtrack.us"""
	
	def get_response(self, request, vrec):
		from django.contrib.auth import authenticate, login
		from django.http import HttpResponse
		user = User.objects.get(id=self.uid)
		authenticate(user_object = user)
		login(request, user)
		return HttpResponse("""<p>Thank you for confirming you still would like to receive updates from GovTrack.</p><p>Continue on to <a href="/">The New GovTrack</a>.</p>""")



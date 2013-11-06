from django.core.management.base import BaseCommand, CommandError

from django.core.mail import send_mail, EmailMultiAlternatives
from django.template import Context, Template
from django.template.loader import get_template
from django.conf import settings

from optparse import make_option

from django.contrib.auth.models import User
from website.models import UserProfile
from emailverification.models import BouncedEmail

from datetime import datetime, timedelta

import yaml, markdown2, re

class Command(BaseCommand):
	args = 'daily|weekly|all|test|count'
	help = 'Sends out an email blast to users with a site announcement.'
	
	def handle(self, *args, **options):
		if len(args) != 1 or args[0] not in ('daily', 'weekly', 'all', 'test', 'count'):
			print "Specify daily or weekly or all or test or count."
			return
			
		# Load current email blast.
			
		blast = load_blast()
		
		# Definitions for the four groups of users.
			
		user_groups = {
			"test": UserProfile.objects.filter(user__email="jt@occams.info"),
			"all": UserProfile.objects.all(),
			"daily": UserProfile.objects.filter(user__subscription_lists__email=1).distinct(),
			"weekly": UserProfile.objects.filter(user__subscription_lists__email=2).distinct(),
		}
		
		# also require:
		# * the mass email flag is turned
		# * we haven't sent them this blast already
		# * they don't have a BouncedEmail record
		for ug, qs in user_groups.items():
			user_groups[ug] = qs.filter(
				massemail=True,
				last_mass_email__lt=blast["id"])\
				.exclude(user__bounced_emails__id__gt=0)
			
		if args[0] == "count":
			# Just print counts by group and exit.
			for ug, qs in user_groups.items():
				print ug, qs.count()
			return
			
		# Get the list of user IDs.
			
		users = list(user_groups[args[0]].order_by("user__id").values_list("user", flat=True))
		
		print "Sending to ", args[0], len(users)
			
		total_emails_sent = 0
		for userid in users:
			if send_blast(userid, blast):
				total_emails_sent += 1
			
			from django import db
			db.reset_queries()
			
		print "sent", total_emails_sent, "emails"

	
def load_blast():
	# get the email's From: header and return path
	emailfromaddr = getattr(settings, 'EMAIL_UPDATES_FROMADDR',
			getattr(settings, 'SERVER_EMAIL', 'no.reply@example.com'))
		
	# Load the Markdown template for the current blast.
	templ = get_template("website/email/blast.md")
	ctx = Context({ })

	# Get the text-only body content, which also includes some email metadata.
	# Replace Markdown-style [text][href] links with the text plus bracketed href.
	ctx.update({ "format": "text", "utm": "" })
	body_text = templ.render(ctx).strip()
	ctx.pop()
	body_text = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1 at \2", body_text)

	# The top of the text content contains metadata in YAML format,
	# with "id" and "subject" required.
	meta_info, body_text = body_text.split("----------", 1)
	meta_info = yaml.load(meta_info)
	body_text = body_text.strip()

	# Get the HTML body content.
	templ_html_wrapper = get_template("website/email/blast.html")
	ctx.update({
		"format": "html",
		"utm": "utm_campaign=govtrack_email_blast&utm_source=govtrack/email_blast&utm_medium=email",
	})
	body_html = templ.render(ctx).strip()
	body_html = markdown2.markdown(body_html)
	ctx.pop()
	ctx.update({ "body": body_html })
	body_html = templ_html_wrapper.render(ctx)
	ctx.pop()
	
	# Store everything in meta_info.
	
	meta_info["from"] = emailfromaddr
	meta_info["body_text"] = body_text
	meta_info["body_html"] = body_html
	
	return meta_info
	
def send_blast(user_id, blast):
	user = User.objects.get(id=user_id)

	emailreturnpath = blast["from"]
	if hasattr(settings, 'EMAIL_UPDATES_RETURN_PATH'):
		emailreturnpath = (settings.EMAIL_UPDATES_RETURN_PATH % user.id)

	email = EmailMultiAlternatives(
		blast["subject"],
		blast["body_text"],
		emailreturnpath,
		[user.email],
		headers = {
			'From': blast["from"]
		}
		)
	email.attach_alternative(blast["body_html"], "text/html")
	
	try:
		print "emailing", user.id, user.email
		email.send(fail_silently=False)
	except Exception as e:
		print user, e
		return False
	
	prof = user.userprofile()
	prof.last_mass_email = blast["id"]
	prof.save()
		
	return True # success


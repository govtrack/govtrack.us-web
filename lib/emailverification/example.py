#!/usr/bin/python

# Boilerplate.

import sys
if len(sys.argv) < 2:
	print "Specify an email address on the command line."
	sys.exit(0)

to_addr = sys.argv[1]

# Callback Code

from django.contrib.auth.models import User
from django.contrib.auth import login
from django.http import HttpResponseRedirect

class MyAction:
	info = None
	
	def email_subject(self):
		return "You Got Mail"
	
	def email_body(self):
		return """Please follow this link:

<URL>

Thanks!"""

	def email_body(self):
		return """Please follow this link:

<URL>

Thanks!"""

	def email_html_template(self):
		return ("emailverification/htmlexample.html", { "info": self.info })

	def get_response(self, request, vrec):
		return HttpResponseRedirect("/")

# Form Submission Code

from emailverification.utils import send_email_verification

axn = MyAction()
axn.info = "This is a sentence passed in through a template context variable."

send_email_verification(to_addr, None, axn)


from django.contrib.auth.models import User
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.http import HttpResponse, HttpResponseServerError
from django.utils import simplejson
from django import forms

import recaptcha.client.captcha

import sys

# due to changes on April 21, 2011, we must use a different api server
if recaptcha.client.captcha.API_SSL_SERVER== "https://api-secure.recaptcha.net":
	# these won't work in newer recaptcha lib because it creates the full path differently
	recaptcha.client.captcha.API_SSL_SERVER="https://www.google.com/recaptcha/api"
	recaptcha.client.captcha.API_SERVER="http://www.google.com/recaptcha/api"
	recaptcha.client.captcha.VERIFY_SERVER="www.google.com/recaptcha/api"

from emailverification.utils import send_email_verification

from settings import RECAPTCHA_PUBLIC_KEY, RECAPTCHA_PRIVATE_KEY
from settings import APP_NICE_SHORT_NAME
from settings import DEBUG

def captcha_html(error = None):
	return recaptcha.client.captcha.displayhtml(RECAPTCHA_PUBLIC_KEY, error = error, use_ssl=True)

def validate_captcha(request):
	# This may have to be the last check in a form because if the captcha succeeds, the user
	# cannot resubmit without a new captcha. (I hope. reCAPTCHA should not be open
	# to replay-attacks.)
	try:
		cx = recaptcha.client.captcha.submit(request.POST["recaptcha_challenge_field"], request.POST["recaptcha_response_field"], RECAPTCHA_PRIVATE_KEY, request.META["REMOTE_ADDR"])
	except Exception, e:
		raise forms.ValidationError("There was an error processing the CAPTCHA.")
	if not cx.is_valid:
		e = forms.ValidationError("Please try the two reCAPTCHA words again. If you have trouble recognizing the words, try clicking the new challenge button to get a new pair of words to type.")
		e.recaptcha_error = cx.error_code
		raise e

def validate_username(value, skip_if_this_user=None, for_login=False, fielderrors=None):
	try:
		value = forms.CharField(min_length=4 if not for_login else None, error_messages = {'min_length': "The username is too short. Usernames must be at least four characters."}).clean(value) # raises ValidationException
		if " " in value:
			raise forms.ValidationError("Usernames cannot contain spaces.")
		if "@" in value:
			raise forms.ValidationError("Usernames cannot contain the @-sign.")
			
		if not for_login:
			users = User.objects.filter(username = value)
			if len(users) > 0 and users[0] != skip_if_this_user:
				raise forms.ValidationError("The username is already taken.")
			
		return value
	except forms.ValidationError, e:
		if fielderrors == None:
			e.source_field = "username"
			raise e
		else:
			fielderrors["username"] = validation_error_message(e)
			return value
	
def validate_password(value, fielderrors=None):
	try:
		value = forms.CharField(min_length=5, error_messages = {'min_length': "The password is too short. It must be at least five characters."}).clean(value)
		if " " in value:
			raise forms.ValidationError("Passwords cannot contain spaces.")	
		return value
	except forms.ValidationError, e:
		if fielderrors == None:
			e.source_field = "password"
			raise e
		else:
			fielderrors["password"] = validation_error_message(e)
			return value
		
def validate_email(value, skip_if_this_user=None, for_login=False, fielderrors=None):
	try:
		value = forms.EmailField(max_length = 75, error_messages = {'max_length': "Email addresses on this site can have at most 75 characters."}).clean(value) # Django's auth_user table has email as varchar(75)
		if not for_login:
			users = User.objects.filter(email = value)
			if len(users) > 0 and users[0] != skip_if_this_user:
				raise forms.ValidationError("If that's your email address, it looks like you're already registered. You can try logging in instead.")
		return value
	except forms.ValidationError, e:
		if fielderrors == None:
			e.source_field = "email"
			raise e
		else:
			fielderrors["email"] = validation_error_message(e)
			return value

class ChangeEmailAddressAction:
	user = None
	newemail = None
	
	def email_subject(self):
		return APP_NICE_SHORT_NAME + ": Verify Your New Address"
	def email_body(self):
		return """To change your """ + APP_NICE_SHORT_NAME + """ account's email address to this address,
please complete the verification by following this link:

<URL>

All the best,

""" + APP_NICE_SHORT_NAME + """
"""

	def get_response(self, request, vrec):
		self.user.email = self.newemail
		self.user.save()
		return render_to_response('registration/email_change_complete.html', context_instance=RequestContext(request))

def change_email_address(user, newaddress):
	axn = ChangeEmailAddressAction()
	axn.user = user
	axn.newemail = newaddress
	send_email_verification(newaddress, None, axn)

def validation_error_message(validationerror):
	# Turns a ValidationException or a ValueError, KeyError into a string.
	if not hasattr(validationerror, "messages"):
		return unicode(validationerror)

	from django.utils.encoding import force_unicode
	#m = e.messages.as_text()
	m = u'; '.join([force_unicode(g) for g in validationerror.messages])
	if m.strip() == "":
		m = "Invalid value."
	return m
	
def json_response(f):
	"""Turns dict output into a JSON response."""
	def g(*args, **kwargs):
		try:
			ret = f(*args, **kwargs)
			if isinstance(ret, HttpResponse):
				return ret
			resp = HttpResponse(simplejson.dumps(ret), mimetype="application/json")
			return resp
		except ValueError, e:
			sys.stderr.write(unicode(e) + "\n")
			return HttpResponse(simplejson.dumps({ "status": "fail", "msg": unicode(e) }), mimetype="application/json")
		except forms.ValidationError, e :
			m = validation_error_message(e)
			sys.stderr.write(unicode(m) + "\n")
			return HttpResponse(simplejson.dumps({ "status": "fail", "msg": m, "field": getattr(e, "source_field", None) }), mimetype="application/json")
		except Exception, e:
			if DEBUG:
				import traceback
				traceback.print_exc()
			else:
				sys.stderr.write(unicode(e) + "\n")
				raise
			return HttpResponseServerError(simplejson.dumps({ "status": "generic-failure", "msg": unicode(e) }), mimetype="application/json")
	return g
	
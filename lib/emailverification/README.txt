Email Verification App for Django
=================================================

This app provides a framework for the workflow where the user
enters an email address, an email is sent to the user with a
verification code link, the user returns to the website via the link,
and then with the email address confirmed some action is taken.

This can be used for user account registration, changing email
addresses on accounts, etc. Compared to django-registration,
this module *doesn't create* the User object until the email
address is verified (this is a framework for verifying the address
before *you* create the User object).

CONFIGURATION

settings.py:

	Add "emailverification" to your Django Apps list.
	
	Optionally set:
		SITE_ROOT_URL = "http://www.example.org" # no trailing slash!
		
		    The default will be "http://%s" % Site.objects.get_current().domain.
		
		SERVER_EMAIL = "MySite <noreply@example.org>"

		    The address from which the verification codes are sent
		    The default is root@localhost.
		
		SERVER_EMAIL is used by several other aspects of Django so you can
		override the address for this project with the EMAILVERIFICATION_FROMADDR
		setting.

Add a record to your URLConf like this:

	(r'^emailverif/', include('emailverification.urls')),

The base of the URLs can be changed.
	
You will probably want to override the templates in

	templates/emailverification

by either editing them in place or copying the emailverification directory
to your site's root templates directory and editing the copies there. There
are two templates: one is for what is shown to the user when they come
with an invalid verification code (or when an error occurs unpickling the
saved state, see below), and one when the verification code has expired.
If the verification code is good, your code is called to return something
to the user.

And don't forget to run python manage.py syncdb to create the necessary
database table.

USAGE

Define a class at the *top-level* of any module which will hold onto the
information the user submitted and the email subject line and body.
It will also contain the Python code to be executed as a "callback" once
the user clicks the verification link. The class should have fields for data
stored with the instance, plus a get_response method that takes two
arguments (besides self): the HttpRequest and the emailverification.Record
object that has just been verified. Here's an example:

=================================================
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.http import HttpResponseRedirect
...
class RegisterUserAction:
	email = None
	username = None
	password = None
	
	def email_subject(self):
		return "[subjectline of email to send user with link]"
	
	def email_body(self):
		return """Thanks for creating an account. To verify your account just follow this link:

<URL>

All the best."""
	
	def get_response(self, request, vrec):
		user = User.objects.create_user(self.username, self.email, self.password)
		user.save()
		login(request, user)
		return HttpResponseRedirect("/home#welcome")
=================================================

Within the string returned by email_body, "<URL>" will be replaced by the
URL that the user should click on to execute the callback action.

In some view in response to the user submitting a form, you'll typically
run this:

=================================================
from emailverification.utils import send_email_verification
...
axn = RegisterUserAction()
axn.email = email
axn.username = username
axn.password = password

send_email_verification(email, None, axn)
=================================================
		
And then just continue processing the view as normal, returning some
template that indicates that the user has just been sent an email. You'll
have to write that part.

send_email_verification will send the user an email with a link back to the
website and will put a random verification code into a table in the database.
The action object will be pickled (serialized) and stored alongside the
verification code in the database. When the user returns with a valid
code that hasn't expired, the action object is unpicked (deserialized) and
its get_response method is called. The default expiration time is seven
days.

The app doesn't prevent verification links from being clicked more than
once. This is by design, since a user might accidentally click on a link
twice (the first time not seeing the response). The response handler
should handle a second call as appropriate. If the callback object
changes any of its state, it will be saved back to the database so on
the second invocation it will get its saved state back. But since requests
are processed asynchronously, there is no guarantee that the state
will be saved before the second request comes in.

Periodically you should issue

	manage.py clear_expired_email_verifications 

to clear out email verification records that have expired.


ADVANCED USE

The action class can optionally contain a method email_from_address
to override the default from address specified either in the
EMAILVERIFICATION_FROMADDR or SERVER_EMAIL settings. e.g.:

=================================================
	def email_from_address(self):
		return "info@example.com"
=================================================

The email can also contain an HTML part. The HTML part is assembled
using the Django templating system. Add a method to the action
class called email_html_template which returns a tuple containing the
name of the template to use and a dict of context variables, e.g.:

=================================================
	def email_html_template(self):
		return ("email/html_template.html", { "message": "Hello!" })
=================================================
		
Typically the template will use {% extends "templatename" %} to apply
a default email theme used across actions.
		
Instead of using "<URL>" in the template, a "URL" context variable will
be set instead, which can be accessed with {{URL|safe}}.

Be careful with adding an HTML part because you might forget to keep
the text and HTML content in sync!

A template can also be used for the text part. Provide a email_text_template
function instead of email_body. email_text_template works the same way
as email_html_template. But be careful because Django will assume that
HTML escaping is still in effect in the template, so any values brought in
via {{...}} should probably be marked as safe, e.g. {{myvariable|safe}},
to avoid HTML escaping.


AUTO-RESENDING EMAILS

The module has a utility to automatically re-send up to twice until a user
clicks the link or clicks an alternative link to stop getting more retries.
Retries are sent for the following records:

	* the record is unexpired (set to 7 days in emailverification.models.EXPIRATION_DAYS)
	* the action object has a method names email_should_resend which returns True.
	* has been neither clicked nor killed
	* the last time the email was sent (either the first time or the most recent retry) is a certain
	  about of time ago, as follows:

	first retry: 15 minutes (since the initial send)
	second retry: 10 hours (since the first retry)
	third retry: 2 days (since the second retry)
	(this is set in emailverification.models.RETRY_DELAYS)
	
To see what retries would be sent, run:

	manage.py resend_email_verifications
	   or
	manage.py resend_email_verifications test
	
It prints one line for each email it would send consisting of:

	* the number of retries already sent
	* the date/time the record was created
	* the date/time of the last email sent (initial or retry)
	* the unicode(...) of the action object for the record
	* the string "test" to indicate this was a dry run
	
To actually send the emails, e.g. from a cron job, run:

	manage.py resend_email_verifications send
	
which prints the same information as in the dry run, except for the string "test"
at the end (nothing is printed in its place).

Re-try emails will only be sent when the action object has a email_should_resend
method that returns True. Use the method to prevent resending an email for
some application-specific reason, such as the action being completed some other
way other than clicking the link in the email. When an action class supports sending
re-tries, it is a good idea to include in the message body an alternative link that
halts sending of future retries. This can be done with either:

	in a plain text body, the substitution string <KILL_URL>
	in a text or HTML template, the context variable KILL_URL

For instance:

=================================================
class RegisterUserAction:
	...
	
	def email_body(self):
		return """Thanks for creating an account. To verify your account just follow this link:

<URL>

All the best.

(We'll send this email again soon in case you miss it the first time. If you do not wish
to complete the action and do not want to get a reminder, please follow this link
instead to stop future reminders: <KILL_URL>)"""
	
	def email_should_resend(self):
		return True
=================================================


A NOTE ON PICKLING

Because this relies on picking, your action object *classes* must be stable
over time. If you delete the class or remove fields from it, unpickling is
going to fail and the user won't be able to continue. (A graceful message
will be displayed.) If you need to make sweeping changes, version your
classes: keep the old ones around indefinitely and add new ones. It is
safe to revise the code, however. So you can change the behavior of
the action so long as you don't change its fields too much. A good
idea might be to forget class fields and use an arbitrary dictionary of
fields, e.g.:

=================================================
class RegisterUserAction:
	fields = None
	def get_response(self, request, vrec):
		user = User.objects.create_user(self.fields["username"], self.fields["email"], self.fields["password"])
		user.save()
		login(request, user)
		return HttpResponseRedirect("/home#welcome")
=================================================

In this case, you don't have to worry about unpickling. Just check for the
keys in the fields property before you use them if you're not sure they
were put there in the first place. But this is a little ugly.

On the other hand, since verification codes expire after seven days, you
are free to delete old classes after that time since those pickled objects
will never be unpickled.



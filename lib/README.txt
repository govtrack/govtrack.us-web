Django Registration App by POPVOX
=================================

This app provides infrastructure for new user registration including support
for social logins (built-in support for Google, Twitter, LinkedIn, and Facebook).
For new user accounts using an email address and password, the user is sent a
confirmation (verification) email *before* the account is created.

The email verification routine can be used as an independent app that provides
an infrastructure for executing callback routines when a user follows a custom
link sent to them in an email. See emailverification/README.txt for details.

Configuration
-------------

Make the icons directory accessible as /media/icons/sm (i.e. social media).

In settings.py, add 'emailverification' and 'registration' to your INSTALLED_APPS.

    APP_NICE_SHORT_NAME = "MySite" # a short name for your site
    SERVER_EMAIL = "MySite <noreply@example.org>" # From: address on verification emails
		
Optionally set:

    SITE_ROOT_URL = "http://www.example.org" # canonical base URL of the site, no trailing slash
                                             # The default will be "http://%s" % Site.objects.get_current().domain
		
Add records to your URLConf like this (you can use any base path):

    (r'^emailverif/', include('emailverification.urls')),
    (r'^registration/', include('registration.urls')),

You will probably also want to use:

    (r'^accounts/login$', 'registration.views.loginform'),
    (r'^accounts/logout$', 'django.contrib.auth.views.logout'),
    (r'^accounts/profile/change_password$', 'django.contrib.auth.views.password_change'),
    (r'^accounts/profile/password_changed$', 'django.contrib.auth.views.password_change_done'),

You will probably want to override the templates in

    emailverification/templates/emailverification
        badcode.html: invalid verification code or an error occurred processing it
        expired.htm: expired verification code

by either editing them in place or copying the directories to your site's
root templates directory and editing the copies there. 

Run python manage.py syncdb to create the necessary database tables.

Beyond this, many of the components of this app are optional. The dependencies
and configuration for the optional parts are given here:

reCAPTCHA on new account creations:

	dependencies:
	
	python-recaptcha <http://pypi.python.org/pypi/recaptcha-client>

	settings.py:

	RECAPTCHA_PUBLIC_KEY = "..."
	RECAPTCHA_PRIVATE_KEY = "..."

Google login with OpenID:

	dependencies:

	python-openid <https://github.com/openid/python-openid>

	No configuration necessary.

Google login with OAuth 1 (not recommended unless you are accessing
the user's Google resources):

	dependencies:

	python-oauth2 <http://github.com/simplegeo/python-oauth2>

	settings.py:

	GOOGLE_OAUTH_TOKEN = "..."
	GOOGLE_OAUTH_TOKEN_SECRET = "..."
	GOOGLE_OAUTH_SCOPE = "http://www.google.com/m8/feeds/contacts/default/full" # can be an empty string

Twitter login with OAuth 1:

	dependencies:

	python-oauth2 <http://github.com/simplegeo/python-oauth2>

	settings.py:

	TWITTER_OAUTH_TOKEN = "..."
	TWITTER_OAUTH_TOKEN_SECRET = "..."

LinkedIn login with OAuth 1:

	settings.py:

	LINKEDIN_API_KEY = "..."
	LINKEDIN_SECRET_KEY = "..."

Facebook login with OAuth 2:

	no dependencies

	settings.py:

	FACEBOOK_APP_ID = "..."
	FACEBOOK_APP_SECRET = "..."
	FACEBOOK_AUTH_SCOPE = "email" # can be an empty string

Copyright
=========

Copyright (C) 2011 POPVOX.com

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation, either version 3 of the
    License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.

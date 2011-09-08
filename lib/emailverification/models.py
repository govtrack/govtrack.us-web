from django.db import models
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse

import settings

import base64
import pickle
import random
from datetime import datetime, timedelta

CODE_LENGTH = 16
EXPIRATION_DAYS = 7
RETRY_DELAYS = [
	timedelta(minutes=15), 	# first retry is 15 minutes
	timedelta(hours=10), 		# second retry is 10 hours after the 1st retry
	timedelta(days=2)] 			# third retry is 2 days after the 2nd retry, after that we give up

class Record(models.Model):
	"""A record is for an email address pending verification, plus the action to take."""
	email = models.EmailField(db_index=True)
	code = models.CharField(max_length=CODE_LENGTH, db_index=True)
	searchkey = models.CharField(max_length=127, blank=True, null=True, db_index=True)
	action = models.TextField()
	created = models.DateTimeField(auto_now_add=True)
	last_send = models.DateTimeField(auto_now_add=True)
	hits = models.IntegerField(default=0)
	retries = models.IntegerField(default=0)
	killed = models.BooleanField(default=False)
	
	def __unicode__(self):
		try:
			a = unicode(self.get_action())
		except:
			a = "(invalid action data)"
		return self.email + ": " + a
		
	def set_code(self):
		self.code = ''.join(random.choice(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z")) for x in range(CODE_LENGTH))

	def set_action(self, action):
		self.action = base64.encodestring(pickle.dumps(action))
		
	def get_action(self):
		return pickle.loads(base64.decodestring(self.action))

	def is_expired(self):
		if (datetime.now() - self.created).days >= EXPIRATION_DAYS:
			return True
		return False
	
	def url(self):
		return getattr(settings, 'SITE_ROOT_URL', "http://%s" % Site.objects.get_current().domain) \
			+ reverse("emailverification.views.processcode", args=[self.code])
	def killurl(self):
		return getattr(settings, 'SITE_ROOT_URL', "http://%s" % Site.objects.get_current().domain) \
			+ reverse("emailverification.views.killcode", args=[self.code])


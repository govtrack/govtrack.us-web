# -*- coding: utf-8 -*-
from django.db import models
from jsonfield import JSONField

import random

class Issue(models.Model):
	"""An issue is something that users might want to weigh in on."""

	slug = models.SlugField(help_text="The slug for this issue in URLs.")
	title = models.CharField(max_length=255, help_text="The issue's display title.")
	question = models.CharField(max_length=255, help_text="The issue phrased as a question.")
	introtext = models.TextField(help_text="Text introducing the issue.")
	positions = models.ManyToManyField('IssuePosition', db_index=True, related_name="issue", help_text="The positions associated with this issue.")
	created = models.DateTimeField(auto_now_add=True, db_index=True, help_text="The date and time the issue was created.")
	isopen = models.BooleanField(default=False, verbose_name="Open", help_text="Whether users can currently participate in this issue.")

	class Meta:
		ordering = ('-created',)

	def __unicode__(self):
		return self.title + "/" + self.question

	def get_absolute_url(self):
		return "/poll/" + self.slug

	def get_randomized_positions(self):
		# Randomize the positions because that's better for polling.
		p = list(self.positions.all())
		random.shuffle(p)
		return p

class IssuePosition(models.Model):
	"""A position that a user can take on an issue."""

	text = models.CharField(max_length=255, help_text="A description of the position.")
	valence = models.NullBooleanField(blank=True, null=True, help_text="The valence of this position, for linking with bills.")
	created = models.DateTimeField(auto_now_add=True, db_index=True, help_text="The date and time the issue was created.")
	call_script = models.TextField(blank=True, null=True, help_text="What you should say when you call your rep about this issue.")

	class Meta:
		ordering = ('-created',)

	def __unicode__(self):
		i = "?"
		try:
			i = self.issue.all()[0].title
		except:
			pass
		v = ""
		if self.valence is True: v = "(+) "
		if self.valence is False: v = "(-) "
		return v + i + " -- " + self.text

class RelatedBill(models.Model):
	"""A bill related to an issue, and possibly a link between support/oppose for the bill and IssuePositions."""

	issue = models.ForeignKey(Issue, db_index=True, related_name="bills", help_text="The related issue.", on_delete=models.CASCADE)
	bill = models.ForeignKey('bill.Bill', db_index=True, help_text="The related bill.", on_delete=models.PROTECT)
	valence = models.NullBooleanField(blank=True, null=True, help_text="The valence of this bill, for linking with IssuePositions. If not null, a user who supports this bill takes the position of the IssuePosition with the same valence value.")

	def __unicode__(self):
		v = ""
		if self.valence is True: v = "(+) "
		if self.valence is False: v = "(-) "
		return v + self.issue.title + " -- " + unicode(self.bill)

class UserPosition(models.Model):
	"""The position of a user on an issue."""

	user = models.ForeignKey('auth.User', db_index=True, help_text="The user who created this position.", on_delete=models.CASCADE)
	position = models.ForeignKey(IssuePosition, db_index=True, help_text="The position the user choses.", on_delete=models.CASCADE)
	created = models.DateTimeField(auto_now_add=True, db_index=True)

	district = models.CharField(max_length=4, db_index=True, help_text="The state and district, in uppercase without any spaces, of the user at the time the user took this posiiton.")

	metadata = JSONField(help_text="Other information stored with the position.")

	def __unicode__(self):
		return unicode(self.user) + "/" + unicode(self.position)

	def get_current_target(self):
		from person.models import PersonRole
		return PersonRole.objects.get(current=True, state=self.district[0:2], district=int(self.district[2:]))

	def can_make_call(self):
		return len(self.district) > 2 # ugh, data collection error

	def can_change_position(self):
		return not CallLog.objects.filter(user=self.user, position=self).exists()


class CallLog(models.Model):
	"""The log of a call to Congress."""

	user = models.ForeignKey('auth.User', db_index=True, help_text="The user who created this call.", on_delete=models.CASCADE)
	position = models.ForeignKey(UserPosition, db_index=True, help_text="The position this call was communicating.", on_delete=models.CASCADE)
	target = models.ForeignKey('person.PersonRole', db_index=True, help_text="The Member of Congress the user called.", on_delete=models.PROTECT)
	created = models.DateTimeField(auto_now_add=True, db_index=True)

	status = models.CharField(max_length=64) # current status of the call

	log = JSONField(help_text="A dict of TwilML information for different parts of the call.")

	class Meta:
		ordering = ('-created',)

	def __unicode__(self):
		return self.created.isoformat() + " " + unicode(self.user) + " " + unicode(self.position)

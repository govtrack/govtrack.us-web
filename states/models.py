# -*- coding: utf-8 -*-
from django.db import models
from django.template.defaultfilters import slugify
from django.core.urlresolvers import reverse

from common import enum
from jsonfield import JSONField

from django.conf import settings

import datetime, os.path

import us

"Enums"

class StateChamberEnum(enum.Enum):
	unknown = enum.Item(0, 'Unknown Chamber')
	unicameral = enum.Item(1, 'Unicameral Chamber')
	lower = enum.Item(2, 'Lower Chamber')
	upper = enum.Item(3, 'Upper Chamber')

"Models"

class StateLegislator(models.Model):
	bt50id = models.IntegerField(unique=True, db_index=True)
	openstatesid = models.CharField(max_length=10, unique=True, db_index=True, blank=True, null=True)
	legiscanid = models.IntegerField(db_index=True, blank=True, null=True) # there are dups
	
	state = models.CharField(max_length=2)
	firstname = models.CharField(max_length=24)
	lastname = models.CharField(max_length=32)
	fullname = models.CharField(max_length=58)
	party = models.CharField(max_length=16)
	
class StateSubjectTerm(models.Model):
	bt50id = models.IntegerField(unique=True, db_index=True)
	state = models.CharField(max_length=2)
	name = models.CharField(max_length=64)

	class Meta:
		ordering = ('state', 'name')
		unique_together = [('state', 'name')]

class StateSession(models.Model):
	state = models.CharField(max_length=2)
	startdate = models.DateField(blank=True, null=True)
	enddate = models.DateField(blank=True, null=True)
	name = models.CharField(max_length=64)
	slug = models.CharField(max_length=12)
	current = models.BooleanField(default=True)

	class Meta:
		ordering = ('state', 'startdate')
		unique_together = [('state', 'name'), ('state', 'slug')]

	def __unicode__(self):
		return us.statenames[self.state] + " " + self.name

from events.models import Feed
Feed.register_feed(
	"states_allbills",
	title = "State Legislation: All Activity",
	slug = "states_bills",
	intro_html = """Use this feed to track all legislative events in all United States state legislatures.""",
	simple = True,
	sort_order = 200
	)
for st in us.stateabbrs:
	Feed.register_feed(
		"states_%s_bills" % st,
		title = us.statenames[st] + " Legislation",
		link = "/states/%s" % st.lower(),
		)
Feed.register_feed(
	"states_bill:",
	title = lambda feed : unicode(StateBill.objects.get(id=feed.feedname.split(":")[1])),
	link = lambda feed : StateBill.objects.get(id=feed.feedname.split(":")[1]).get_absolute_url(),
	)

class StateBill(models.Model):
	bt50id = models.IntegerField(unique=True, db_index=True)
	openstatesid = models.CharField(max_length=32, unique=True, db_index=True, blank=True, null=True)
	legiscanid = models.IntegerField(unique=True, db_index=True, blank=True, null=True)
	
	state_session = models.ForeignKey(StateSession)
	bill_number = models.CharField(max_length=16)
	chamber = models.IntegerField(choices=StateChamberEnum)
	
	short_title = models.CharField(max_length=255)
	long_title = models.CharField(max_length=255)
	summary = models.TextField()
	
	introduced_date = models.DateField(blank=True, null=True)
	last_action_date = models.DateField(blank=True, null=True)
	last_action_seq = models.IntegerField(blank=True, null=True)
	last_action_text = models.CharField(max_length=128, blank=True, null=True)

	sponsors = models.ManyToManyField(StateLegislator, blank=True, related_name="sponsored_bills")
	cosponsors = models.ManyToManyField(StateLegislator, blank=True, related_name="cosponsored_bills")
	
	subjects = models.ManyToManyField(StateSubjectTerm, blank=True)
	
	srchash = models.CharField(max_length=40)
	
	class Meta:
		ordering = ('state_session', 'bill_number', 'chamber')
		unique_together = [('state_session', 'bill_number', 'chamber')]
		
	def __unicode__(self):
		return self.short_display_title
		
	def get_absolute_url(self):
		return "/states/%s/bills/%s/%s" % (self.state_session.state.lower(), self.state_session.slug, self.bill_number.lower())
		
	# indexing
	def get_index_text(self):
		return self.long_title + "\n" + self.short_title + "\t" + self.summary
	haystack_index = ('state_session', 'bill_number', 'chamber')
	haystack_index_extra = (('state', 'Char'),)

	def state_name(self): return us.statenames[self.state_session.state]

	@property
	def short_display_title(self):
		return self.state_session.state + " " + self.state_session.slug + " " + self.bill_number + ". " + self.short_title
		
	@property
	def is_current(self):
		return self.state_session.current
		
	def state(self): return self.state_session.state
	def session(self): return self.state_session.name

	def create_events(self):
		# don't create events too far in the past because they will never be used
		if not self.introduced_date: return
		if self.introduced_date.year < 2012: return
		
		# What feeds will we file events for this bill under?
		#   a) The 50-state-legislation feed.
		#   b) The state-wide legislation feed.
		#   c) The bill's feed.
		
		from events.models import Feed, Event
		
		AllBills, is_new = Feed.objects.get_or_create(feedname="states_allbills")
		StateBills, is_new = Feed.objects.get_or_create(feedname="states_%s_bills" % self.state_session.state)
		ThisBill, is_new = Feed.objects.get_or_create(feedname="states_bill:%d" % self.id)
		our_feeds = [AllBills, StateBills, ThisBill]
		
		with Event.update(self) as E:
			for axn in self.actions.all(): # natural sort order should be preserved
				E.add("axn:" + str(axn.id), axn.date, our_feeds)
	
	def render_event(self, eventid, feeds):
		axn = StateBillAction.objects.get(id=eventid.split(":")[1])
		return {
			"type": "State Legislative Action",
			"date": axn.date,
			"date_has_no_time": True,
			"title": axn.bill,
			"url": axn.bill.get_absolute_url(),
			"body_text_template": "{{event|safe}}",
			"body_html_template": "{{event}}",
			"context": {
				"event": axn.text,
				},
			}
			
			
class StateBillAction(models.Model):
	bt50id = models.IntegerField(unique=True, db_index=True)
	
	bill = models.ForeignKey(StateBill, related_name="actions", db_index=True)
	seq = models.IntegerField()
	date = models.DateTimeField()
	text = models.TextField()

	class Meta:
		ordering = ('bill', 'date', 'seq')
		unique_together = [('bill', 'date', 'seq')] # actually not unique, must update in MySQL
		
			
class StateBillDocument(models.Model):
	bt50id = models.IntegerField(unique=True, db_index=True)
	
	bill = models.ForeignKey(StateBill, related_name="documents", db_index=True)
	type = models.CharField(max_length=16)
	url = models.CharField(max_length=256)

	class Meta:
		ordering = ('bill',)


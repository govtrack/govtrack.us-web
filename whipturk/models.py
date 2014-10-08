# -*- coding: utf-8 -*-
from django.db import models
from jsonfield import JSONField
from common import enum

import random

MAX_CALLS_TO_TARGET = 50
MAX_CALLS_FROM_USER = 50
MAX_CALLS_TO_TARGET_ON_BILL = 3
MAX_CALLS_TO_TARGET_FROM_USER = 3

class WhipReportType(enum.Enum):
	self_report = enum.Item(1, 'Self Report')
	cited_source = enum.Item(2, 'Cited Source')
	phone_call = enum.Item(3, 'Phone Call')

class WhipReportResult(enum.Enum):
	invalid = enum.Item(0, 'Invalid')
	not_entered = enum.Item(1, 'Not Entered')
	unknown = enum.Item(2, 'No Information Found')
	no_position = enum.Item(3, 'Member Has No Position')
	supports = enum.Item(4, 'Member Supports The Bill')
	opposes = enum.Item(5, 'Member Opposes The Bill')
	its_complicated = enum.Item(6, 'It\'s Complicated')
	got_voicemail = enum.Item(7, 'Got Voicemail')
	asked_to_call_back = enum.Item(8, 'Asked To Call Back')

class WhipReportReviewStatus(enum.Enum):
	not_reviewed = enum.Item(0, 'Not Reviewed')
	ok = enum.Item(1, 'OK')
	bad = enum.Item(2, 'Bad')
	
class WhipReport(models.Model):
	"""The result of calling Congress for information about a Member's position on a bill."""

	user = models.ForeignKey('auth.User', db_index=True, help_text="The user making the phone call or reporting the information.", on_delete=models.PROTECT)
	bill = models.ForeignKey('bill.Bill', db_index=True, help_text="The bill the call was about.", on_delete=models.PROTECT)
	target = models.ForeignKey('person.PersonRole', db_index=True, help_text="The Member of Congress called.", on_delete=models.PROTECT)

	report_type = models.IntegerField(choices=WhipReportType, help_text="The nature of the report being made.")
	report_result = models.IntegerField(choices=WhipReportResult, default=WhipReportResult.invalid, help_text="The information gleaned by this report.")
	review_status = models.IntegerField(choices=WhipReportReviewStatus, default=WhipReportReviewStatus.not_reviewed, help_text="The information gleaned by this report.")

	citation_url = models.CharField(max_length=256, blank=True, null=True)
	citation_title = models.CharField(max_length=256, blank=True, null=True)
	citation_date = models.DateField(blank=True, null=True, help_text="The date on which the reported information was valid, if different from the creation date of this report.")

	created = models.DateTimeField(auto_now_add=True, db_index=True, help_text="The date and time the report was filed.")
	updated = models.DateTimeField(auto_now=True, help_text="The date and time the report was filed.")

	call_status = models.CharField(max_length=64, blank=True, null=True) # status of a Twilio call in progress
	call_log = JSONField(blank=True, null=True, help_text="A dict of TwilML information for different parts of the call.")

	class Meta:
		ordering = ('-created',)

	def has_made_successful_call(self):
		return isinstance(self.call_log, dict) and self.call_log.get("finished", {}).get("RecordingUrl") is not None

	def get_result_description(self):
		return WhipReport.get_result_nice_text(self.report_result, self.bill, self.target)

	def get_result_options(self):
		return sorted(
			(kv[0], WhipReport.get_result_nice_text(kv[0], self.bill, self.target))
			for kv in list(WhipReportResult)
			if kv[0] != WhipReportResult.invalid
			)

	@staticmethod
	def get_result_nice_text(report_result, bill, target):
		if report_result == WhipReportResult.invalid:
			return "The call was not completed."
		if report_result == WhipReportResult.not_entered:
			return "The result of the call has not yet been entered."
		if report_result == WhipReportResult.unknown:
			return "No useful information was gathered by this call."
		if report_result == WhipReportResult.no_position:
			return "%s does not have a position on %s." % (target.person.name_no_details(), bill.display_number)
		if report_result == WhipReportResult.supports:
			return "%s supports %s." % (target.person.name_no_details(), bill.display_number)
		if report_result == WhipReportResult.opposes:
			return "%s opposes %s." % (target.person.name_no_details(), bill.display_number)
		if report_result == WhipReportResult.its_complicated:
			return "%s does not have a simple position on %s." % (target.person.name_no_details(), bill.display_number)
		if report_result == WhipReportResult.got_voicemail:
			return "You got voicemail."
		if report_result == WhipReportResult.asked_to_call_back:
			return "You were asked to call back at another time."

	def should_set_result(self):
		return self.report_result == WhipReportResult.not_entered

	def can_set_result(self):
		return self.report_result != WhipReportResult.invalid

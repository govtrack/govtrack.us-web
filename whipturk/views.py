# -*- coding: utf-8 -*-
from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.conf import settings

from common.decorators import render_to

from datetime import datetime

from whipturk.models import *

from bill.models import Bill, Cosponsor
from person.models import PersonRole, RoleType
from person.analysis import load_sponsorship_analysis2

from twostream.decorators import anonymous_view, user_view_for
from registration.helpers import json_response

targets_by_chamber = {
	
}

def get_targets_by_chamber(chamber):
	if chamber not in targets_by_chamber:
		# Get all current representatives or all senators.
		role_type = RoleType.representative if chamber == "house" else RoleType.senator
		targets = PersonRole.objects.filter(
			current=True,
			role_type=role_type)\
			.exclude(phone=None)\
			.select_related('person')

		# Create a priority score for each. We prefer to first call
		# legislators in the middle of the ideology spectrum because
		# they are least predictable, and also we prefer to call leaders
		# because they are more important.
		analysis = load_sponsorship_analysis2(settings.CURRENT_CONGRESS, role_type, None)
		target_priorities = { }

		all_ideology_scores = [float(p["ideology"]) for p in analysis["all"]]
		mean_ideology = sum(all_ideology_scores) / float(len(analysis["all"]))
		absmax_ideology = max(abs(max(all_ideology_scores)-mean_ideology), abs(min(all_ideology_scores)-mean_ideology))

		for p in analysis["all"]:
			score = float(p["leadership"]) - abs(float(p["ideology"]) - mean_ideology)/absmax_ideology
			target_priorities[p["id"]] = score

		targets_by_chamber[chamber] = [
			(target, target_priorities.get(target.person.id, 0.0))
			for target in targets
		]

	return targets_by_chamber[chamber]

def choose_bill():
	# What shall we ask the user to call about?
	bill_id = 286265
	return Bill.objects.get(id=bill_id)

def choose_target(bill, user):
	# Who could we ask the user to call?
	chamber = bill.current_chamber
	if chamber == None:
		# It's not pending any action. This is bad.
		return None
	targets = get_targets_by_chamber(chamber)
	target_scores = dict(targets)

	# Remove the sponsor and cosponsors --- we know their positions.
	if bill.sponsor_role in target_scores:
		del target_scores[bill.sponsor_role]
	for cosp in Cosponsor.objects.filter(bill=bill):
		if cosp.role in target_scores:
			del target_scores[cosp.role]

	# Adjust scores by whether the target has been called before, and
	# especially if this user made that call.
	for wr in WhipReport.objects.filter(bill=bill):
		if wr.target in target_scores:
			target_scores[wr.target] -= 1.0
			if wr.user == user:
				target_scores[wr.target] -= 1.0

	# Bump score if this is the user's rep.
	cd = user.userprofile().congressionaldistrict
	for target in target_scores:
		if cd and target.state == cd[0:2] and (target.role_type == RoleType.senator or int(cd[2:]) == target.district):
			target_scores[target] += 1.0

	# Take target with maximal score.
	return max(target_scores, key = lambda t : target_scores[t])

@login_required
@render_to('whipturk/my_calls.html')
def my_calls(request):
	return {
		"calls": WhipReport.objects.filter(user=request.user),
	}

@login_required
@render_to('whipturk/place_call.html')
def start_call(request):
	bill = choose_bill()
	target = choose_target(bill, request.user)
	if bill is None or target is None:
		# Can't make a call now. Errr....
		return redirect('/publicwhip/my-calls')

	return {
		"bill": bill,
		"target": target,
		"goodtime": (0 <= datetime.now().weekday() <= 4) and (9 <= datetime.now().time().hour <= 16),
	}

@login_required
@json_response
def dial(request):
	bill = get_object_or_404(Bill, id=request.POST["bill"])
	target = get_object_or_404(PersonRole, id=request.POST["target"])

	# basic abuse prevention
	if WhipReport.objects.filter(bill=bill, target=target).count() > MAX_CALLS_TO_TARGET_ON_BILL:
		return { "ok": False, "msg": "We've already made enough calls like that." }
	if WhipReport.objects.filter(user=request.user, target=target).count() > MAX_CALLS_TO_TARGET_FROM_USER:
		return { "ok": False, "msg": "You've already made enough calls like that." }
	if WhipReport.objects.filter(user=request.user).count() > MAX_CALLS_FROM_USER:
		return { "ok": False, "msg": "You've already made enough calls like that." }
	if WhipReport.objects.filter(target=target).count() > MAX_CALLS_TO_TARGET:
		return { "ok": False, "msg": "We've already made enough calls like that." }

	# basic validation of user's phone number
	phone_num = "".join(c for c in request.POST["phone_number"] if unicode.isdigit(c)).encode("ascii")
	if len(phone_num) != 10:
		return { "ok": False, "msg": "Enter your area code and phone number." }

	# initialize twilio client
	try:
		from twilio.rest import TwilioRestClient
		client = TwilioRestClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
	except Exception as e:
		return { "ok": False, "msg": "Site error: " + str(e) }

	# start a new report
	report = WhipReport.objects.create(
		user=request.user,
		bill=bill,
		target=target,
		report_type=WhipReportType.phone_call,
		call_status="not-yet-started",
		call_log={})

	call = client.calls.create(
		to=("+1" + phone_num),
        from_=settings.TWILIO_OUR_NUMBER,
        url=build_twilio_callback_url(request, report, "call-start"),
        status_callback=build_twilio_callback_url(request, report, "call-end"),
        )

	report.call_log["sid"] = call.sid
	report.call_status = "started"
	report.save()

	return { "ok": True, "call_id": report.id }
	
def build_twilio_callback_url(request, report, method):
	return request.build_absolute_uri("/publicwhip/_twilio/%s/%d" % (method, report.id))

@login_required
@json_response
def call_status(request):
	report = get_object_or_404(WhipReport, id=request.POST["id"], user=request.user)

	if report.call_status == "not-yet-started":
		msg = "Something went wrong, sorry!"
	elif report.call_status == "started":
		msg = "We are dialing your number..."
	elif report.call_status == "picked-up":
		msg = "You picked up. Dial 1 to be connected."
	elif report.call_status == "connecting":
		msg = "Connecting you to Congress..."
	elif report.call_status == "connection-ended":
		msg = "Ending the call... Hang on..."
	elif report.call_status == "ended":
		msg = "Call ended. Hang on..."

	return { "finished": report.call_status == "ended", "msg": msg }

from twilio.twiml import Response as TwilioResponse
from django_twilio.decorators import twilio_view

def get_request_log_info(request):
	log_meta_fields = ('REMOTE_ADDR', 'HTTP_COOKIE')
	ret = { f: request.META.get(f) for f in log_meta_fields }
	ret["time"] = datetime.now().isoformat()
	return ret

@twilio_view
def twilio_callback(request, method, call_id):
	# Dynamically invoke one of the methods below.
	import whipturk.views
	return getattr(whipturk.views, "twilio_call_" + method.replace("-", "_"))(request, call_id)

def twilio_call_start(request, call_id):
	report = get_object_or_404(WhipReport, id=int(call_id))
	report.call_status = "picked-up"
	report.call_log["start"] = dict(request.POST)
	report.call_log["start"]["_request"] = get_request_log_info(request)
	report.save()

	resp = TwilioResponse()
	resp.say("Hello from Gov Track.")
	g = resp.gather(
            action=build_twilio_callback_url(request, report, "call-input"),
            numDigits=1,
            timeout=20,
            )
	g.say("Press one to be connected to the office of %s %s. Press two if you did not request this call. Or simply hang up if you do not want your call to be connected." % (
			report.target.get_title(),
			report.target.person.lastname))
	resp.say("Oooo too slow. We're going to hang up now.")

	return resp

def twilio_call_input(request, call_id):
	report = get_object_or_404(WhipReport, id=int(call_id))
	digit = request.POST["Digits"]

	report.call_log["input"] = dict(request.POST)
	report.call_log["input"]["_request"] = get_request_log_info(request)

	resp = TwilioResponse()

	if digit != "1":
		# basically an abuse report
		report.call_log["input"]["response"] = "did-not-request-call"
		resp.say("We apologize for the inconvenience. Call 202-558-7227 or visit w w w dot gov track dot u s to report abuse. Good bye.")
		resp.hangup()

	elif settings.DEBUG:
		resp.say("Site is in debug mode. Call cancelled.")
		resp.hangup()

	else:
		phone = "+1" + "".join(c for c in report.target.phone if unicode.isdigit(c))

		report.call_log["input"]["response"] = "continue"
		report.call_log["input"]["transfer_to"] = phone

		resp.say("Okay. Hold on.")
		resp.dial(
			phone,
            action=build_twilio_callback_url(request, report, "call-transfer-end"),
            timeout=30,
            callerId=request.POST["To"],
            record=True,
			)

	report.call_status = "connecting"
	report.save()

	return resp

def twilio_call_transfer_end(request, call_id):
	report = get_object_or_404(WhipReport, id=int(call_id))
	report.call_status = "connection-ended"
	report.call_log["finished"] = dict(request.POST)
	report.call_log["finished"]["_request"] = get_request_log_info(request)
	report.save()

	resp = TwilioResponse()
	resp.say("Your call to Congress has ended. Thank you for being a great citizen. Goodbye.")
	return resp

def twilio_call_end(request, call_id):
	report = get_object_or_404(WhipReport, id=int(call_id))
	report.call_status = "ended"
	report.call_log["end"] = dict(request.POST)
	report.call_log["end"]["_request"] = get_request_log_info(request)
	report.report_result = WhipReportResult.not_entered
	report.save()

	# empty response
	resp = TwilioResponse()
	return resp

@login_required
@json_response
def update_report(request):
	report = get_object_or_404(WhipReport, id=request.POST['report'], user=request.user)
	report.report_result = int(request.POST['value'])
	report.save()
	return { "status": "ok" }

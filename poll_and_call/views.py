# -*- coding: utf-8 -*-
from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import redirect, get_object_or_404
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.db.models import Count, F

from common.decorators import render_to

from poll_and_call.models import Issue, IssuePosition, UserPosition, CallLog
from person.models import PersonRole

from twostream.decorators import anonymous_view, user_view_for
from registration.helpers import json_response

from datetime import datetime

@anonymous_view
@render_to('poll_and_call/issue_details.html')
def issue_show(request, issue_slug):
	issue = get_object_or_404(Issue, slug=issue_slug)

	# get the positions, and map ID to the position object
	positions = issue.positions.all()
	pos_map = dict({ p.id: p for p in positions })

	# get the current poll results (set default values first)
	for p in positions:
		p.total_users = 0
		p.percent_users = 0
	results = UserPosition.objects.filter(position__issue=issue).values("position").annotate(count=Count('id'))
	total_users = sum(r["count"] for r in results)
	for r in results:
		p = pos_map[r["position"]]
		p.total_users = r["count"]
		p.percent_users = int(round(100.0*r["count"]/total_users))

	return { "issue": issue, "positions": positions, "total_users": total_users }

@user_view_for(issue_show)
def issue_show_user_view(request, issue_slug):
	issue = get_object_or_404(Issue, slug=issue_slug)
	D = { }
	if request.user.is_authenticated():
		try:
			up = UserPosition.objects.get(user=request.user, position__issue=issue)
			targets = up.get_current_targets()
			D["position"] =  {
				"id": up.position.id,
				"text": up.position.text,
				"can_change": up.can_change_position(),
				"can_call": [(t.id, t.person.name) for t in targets] if isinstance(targets, list) else [],
			}
		except:
			pass
	return D

@login_required
@render_to('poll_and_call/issue_join.html')
def issue_join(request, issue_slug, position_id):
	issue = get_object_or_404(Issue, slug=issue_slug)
	try:
		position = issue.positions.get(id=position_id)
	except IssuePosition.DoesNotExist:
		raise Http404()

	try:
		up = UserPosition.objects.get(user=request.user, position__issue=issue)
		if up.can_change_position():
			# User can change his position. Delete the old position before going on.
			up.delete()
		else:
			# The position is fixed. Go on to making a call.
			return HttpResponseRedirect(issue.get_absolute_url() + "/make_call")
	except UserPosition.DoesNotExist:
		pass

	if request.method == "POST":
		# This is a confirmation.

		# Create the new position.
		UserPosition.objects.create(
			user=request.user,
			position=position,
			district=request.POST.get("district"),
			metadata={
				"choice_display_index": request.GET.get("meta_order"),
			})
		return HttpResponseRedirect(issue.get_absolute_url() + "/make_call")

	return { "issue": issue, "position": position }

@login_required
@render_to('poll_and_call/issue_make_call.html')
def issue_make_call(request, issue_slug):
	issue = get_object_or_404(Issue, slug=issue_slug)
	user_position = get_object_or_404(UserPosition, user=request.user, position__issue=issue)

	# is there a representative to call in the user's district that the user hasn't called?
	targets = user_position.get_current_targets()
	if isinstance(targets, str):
		return HttpResponseRedirect(issue.get_absolute_url() + "#" + targets)

	# choose a target at random
	rep = targets[0]

	# if 'target' is a GET parameter, call that target.
	try:
		rep = [t for t in targets if t.id == int(request.GET['target'])][0]
	except:
		# target is not a parameter, is not an integer, is not one of the targets
		pass

	# is this a good time of day to call?
	#if not ((0 <= datetime.now().weekday() <= 4) and ('09:15' <= datetime.now().time().isoformat() <= '16:45')):
	#	return HttpResponseRedirect(issue.get_absolute_url() + "#hours")

	position = user_position.position
	position.call_script = dynamic_call_script(issue, position, rep.person, rep)

	next_step = issue.get_absolute_url()
	for bill in issue.bills.all():
		next_step = bill.bill.get_absolute_url()

	return {
		"issue": issue,
		"user_position": user_position,
		"position": position,
		"moc": rep,
		"other_targets": [t for t in targets if t != rep],
		"next_step": next_step,
		}

def dynamic_call_script(issue, position, person, role):
	name = role.get_title() + " " + person.lastname

	from person.types import Gender
	pos_pro = Gender.by_value(person.gender).pronoun_posessive

	if issue.slug == "gov-shutdown-2013" and position.valence is True:
		if role.party == "Democrat":
			return position.call_script + " I ask %s to be open to a repeal or delay of the Affordable Care Act." % (name,)
		elif role.party == "Republican":
			return position.call_script + " I ask %s to hold %s ground until the Democrats come to the table to negotiate." % (name, pos_pro)
	elif issue.slug == "gov-shutdown-2013" and position.valence is False:
		if role.party == "Democrat":
			return position.call_script + " I ask %s to hold %s ground until the Republicans agree to fund the government." % (name, pos_pro)
		elif role.party == "Republican":
			return position.call_script + " I ask %s to pass a clean CR." % (name,)
	elif issue.slug == "debt-ceiling-2013":
			return position.call_script % (name,)
	return position.call_script

def twilio_client():
	from twilio.rest import TwilioRestClient
	return TwilioRestClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

@login_required
@json_response
def start_call(request):
	user_position = get_object_or_404(UserPosition, id=request.POST["p"], user=request.user)

	# validate the 'target' parameter
	possible_targets = user_position.get_current_targets()
	if isinstance(possible_targets, str): return { "ok": False, "msg": "There is no one for you to call." }
	try:
		target = [t for t in possible_targets if t.id == int(request.POST['target'])][0]
	except:
		return { "ok": False, "msg": "You cannot call that office." }

	# basic phone number validation
	phone_num = "".join(c for c in request.POST["phone_number"] if unicode.isdigit(c)).encode("ascii")
	if len(phone_num) != 10:
		return { "ok": False, "msg": "Enter your area code and phone number." }

	try:
		client = twilio_client()
	except Exception as e:
		return { "ok": False, "msg": "Site error: " + str(e) }

	cl = CallLog.objects.create(
		user=request.user,
		position=user_position,
		target=target,
		status="not-yet-started",
		log={})

	call = client.calls.create(
		to=("+1" + phone_num),
        from_=settings.TWILIO_OUR_NUMBER,
        url=request.build_absolute_uri("/poll/_twilio/call-start/" + str(cl.id)),
        status_callback=request.build_absolute_uri("/poll/_twilio/call-end/" + str(cl.id)),
        )

	cl.log["sid"] = call.sid
	cl.status = "started"
	cl.save()

	return { "ok": True, "call_id": cl.id }
	
#	except Exception as e:
#		return { "ok": False, "msg": "Something went wrong, sorry!", "error": repr(e) }

@login_required
@json_response
def poll_call_status(request):
	call_log = get_object_or_404(CallLog, id=request.POST["id"], user=request.user)

	if call_log.status == "not-yet-started":
		msg = "Something went wrong, sorry!"
	elif call_log.status == "started":
		msg = "We are dialing your number..."
	elif call_log.status == "picked-up":
		msg = "You picked up. Dial 1 to be connected."
	elif call_log.status == "connecting":
		msg = "Connecting you to Congress..."
	elif call_log.status == "connection-ended":
		msg = "Ending the call..."
	elif call_log.status == "ended":
		msg = "Call ended."

	return { "finished": call_log.status == "ended", "msg": msg }

from twilio.twiml.voice_response import VoiceResponse as TwilioResponse
from django_twilio.decorators import twilio_view

def get_request_log_info(request):
	log_meta_fields = ('REMOTE_ADDR', 'HTTP_COOKIE')
	ret = { f: request.META.get(f) for f in log_meta_fields }
	ret["time"] = datetime.now().isoformat()
	return ret

@twilio_view
def twilio_call_start(request, calllog_id):
	call_log = get_object_or_404(CallLog, id=int(calllog_id))
	call_log.status = "picked-up"
	call_log.log["start"] = dict(request.POST)
	call_log.log["start"]["_request"] = get_request_log_info(request)
	call_log.save()

	resp = TwilioResponse()
	resp.say("Hello from Gov Track.")
	g = resp.gather(
            action=request.build_absolute_uri("/poll/_twilio/call-input/" + str(call_log.id)),
            numDigits=1,
            timeout=20,
            )
	g.say("Press one to be connected to the office of %s %s. Press two if you did not request this call. Or simply hang up if you do not want your call to be connected." % (
			call_log.target.get_title(),
			call_log.target.person.lastname))
	resp.say("Oooo too slow. We're going to hang up now.")

	return resp

@twilio_view
def twilio_call_input(request, calllog_id):
	call_log = get_object_or_404(CallLog, id=int(calllog_id))
	digit = request.POST["Digits"]

	call_log.log["input"] = dict(request.POST)
	call_log.log["input"]["_request"] = get_request_log_info(request)

	resp = TwilioResponse()

	if digit != "1":
		# basically an abuse report
		call_log.log["input"]["response"] = "did-not-request-call"
		resp.say("We apologize for the inconvenience. Call 202-558-7227 or visit w w w dot gov track dot u s to report abuse. Good bye.")
		resp.hangup()

	elif settings.DEBUG:
		resp.say("Site is in debug mode. Call cancelled.")
		resp.hangup()

	else:
		phone = "+1" + "".join(c for c in call_log.target.phone if unicode.isdigit(c))

		call_log.log["input"]["response"] = "continue"
		call_log.log["input"]["transfer_to"] = phone

		resp.say("Okay. Hold on.")
		resp.dial(
			phone,
            action=request.build_absolute_uri("/poll/_twilio/call-transfer-end/" + str(call_log.id)),
            timeout=30,
            callerId=request.POST["To"],
            record=True,
			)

	call_log.status = "connecting"
	call_log.save()

	return resp

@twilio_view
def twilio_call_transfer_ended(request, calllog_id):
	call_log = get_object_or_404(CallLog, id=int(calllog_id))
	call_log.status = "connection-ended"
	call_log.log["finished"] = dict(request.POST)
	call_log.log["finished"]["_request"] = get_request_log_info(request)
	call_log.save()

	resp = TwilioResponse()
	resp.say("Your call to Congress has ended. Thank you for being a good citizen. Goodbye.")
	return resp

@twilio_view
def twilio_call_end(request, calllog_id):
	call_log = get_object_or_404(CallLog, id=int(calllog_id))
	call_log.status = "ended"
	call_log.log["end"] = dict(request.POST)
	call_log.log["end"]["_request"] = get_request_log_info(request)
	call_log.save()

	# empty response
	resp = TwilioResponse()
	return resp

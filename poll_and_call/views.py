# -*- coding: utf-8 -*-
from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import redirect, get_object_or_404
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.db.models import Count, F

from common.decorators import render_to

from poll_and_call.models import Issue, IssuePosition, UserPosition

from twostream.decorators import anonymous_view, user_view_for

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
		p.percent_users = 100*r["count"]/total_users

	return { "issue": issue, "positions": positions, "total_users": total_users }

@user_view_for(issue_show)
def issue_show_user_view(request, issue_slug):
	issue = get_object_or_404(Issue, slug=issue_slug)
	D = { }
	if request.user.is_authenticated():
		try:
			up = UserPosition.objects.get(user=request.user, position__issue=issue)
			D["position"] =  { "id": up.position.id, "text": up.position.text }
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

	if request.method == "POST":
		# This is a confirmation.
		UserPosition.objects.filter(user=request.user, position__issue=issue).delete()
		UserPosition.objects.create(
			user=request.user,
			position=position,
			district=request.POST.get("district"),
			metadata={
				"choice_display_index": request.GET.get("meta_order"),
			})
		return HttpResponseRedirect(issue.get_absolute_url())

	return { "issue": issue, "position": position }

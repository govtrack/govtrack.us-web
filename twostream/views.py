# -*- coding: utf-8 -*-
from django.http import HttpResponse, Http404
from django.urls import resolve
from django.template import Template, RequestContext
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie

import json

head_template_mime_type = "application/javascript"
head_template = Template("""
$(document).ajaxSend(function(event, xhr, settings) { if (!/^https?:.*/.test(settings.url)) xhr.setRequestHeader("X-CSRFToken", "{{csrf_token|escapejs}}"); });
var the_user = {{user_data|safe}};
var the_page = {{page_data|safe}};
{% include "user_head_script.js" %}
""")

@cache_control(private=True, must_revalidate=True)
@ensure_csrf_cookie
def user_head(request):
	m = resolve(request.GET.get("path", request.GET.get("view", "")))
	
	user_data = None
	if request.user.is_authenticated:
		user_data = { "id": request.user.id, "email": request.user.email }
		if hasattr(request.user, 'twostream_data'):
			user_data.update(request.user.twostream_data)
		
	page_data = None
	if hasattr(m.func, 'user_func'):
		try:
			page_data = m.func.user_func(request, *m.args, **m.kwargs)
		except Http404:
			# silently ignore, probably the main page was a 404 too
			pass

	return HttpResponse(head_template.render(RequestContext(request, {
				"csrf_token": request.META.get("CSRF_COOKIE") or "",
				"user": request.user,
				"user_data": json.dumps(user_data),
				"page_data": json.dumps(page_data),
				})), content_type=head_template_mime_type)
	

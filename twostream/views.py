# -*- coding: utf-8 -*-
from django.http import HttpResponse
from django.core.urlresolvers import resolve
from django.template import Template, Context, RequestContext

import json

head_template = Template("""
$('html').ajaxSend(function(event, xhr, settings) { if (!/^https?:.*/.test(settings.url)) xhr.setRequestHeader("X-CSRFToken", "{{csrf_token|escapejs}}"); });
var the_user = {{user_data|safe}};
{% include "use_head_script.js" %}
""")

def user_head(request):
	m = resolve(request.GET["view"])
	
	user_data = None
	if request.user.is_authenticated():
		user_data = { "email": request.user.email }
	
	return HttpResponse(head_template.render(RequestContext(request, {
				"user_data": json.dumps(user_data),
				})))
	

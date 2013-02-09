# -*- coding: utf-8 -*-
from django.http import HttpResponse
from django.core.urlresolvers import resolve
from django.template import Template, Context, RequestContext
from django.views.decorators.cache import cache_control

import json

head_template_mime_type = "application/javascript"
head_template = Template("""
$('html').ajaxSend(function(event, xhr, settings) { if (!/^https?:.*/.test(settings.url)) xhr.setRequestHeader("X-CSRFToken", "{{csrf_token|escapejs}}"); });
var the_user = {{user_data|safe}};
var the_page = {{page_data|safe}};
{% include "user_head_script.js" %}
""")

@cache_control(private=True, must_revalidate=True)
def user_head(request):
	m = resolve(request.GET["path"])
	
	user_data = None
	if request.user.is_authenticated():
		user_data = { "email": request.user.email }
		
	page_data = None
	if hasattr(m.func, 'user_func'):
		page_data = m.func.user_func(request, *m.args, **m.kwargs)
	
	return HttpResponse(head_template.render(RequestContext(request, {
				"user_data": json.dumps(user_data),
				"page_data": json.dumps(page_data),
				})), content_type=head_template_mime_type)
	

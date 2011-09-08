from django.http import HttpResponseServerError
from django.shortcuts import render_to_response
from django.template import RequestContext

import datetime

from models import *

from settings import DEBUG

def processcode(request, code):
	try:
		rec = Record.objects.get(code=code)
	except:
		return render_to_response('emailverification/badcode.html', { "code": code }, context_instance=RequestContext(request))

	if rec.is_expired():
		return render_to_response('emailverification/expired.html',  context_instance=RequestContext(request))

	rec.hits += 1
	rec.save() # save early in case view raises an exception

	axn = rec.get_action()
		
	ret = axn.get_response(request, rec)
		
	rec.set_action(axn)
	rec.save()
		
	return ret
	
def killcode(request, code):
	try:
		rec = Record.objects.get(code=code)
	except:
		return render_to_response('emailverification/badcode.html', { "code": code }, context_instance=RequestContext(request))

	rec.killed = True
	rec.save()

	return render_to_response('emailverification/codekilled.html', { "code": code }, context_instance=RequestContext(request))


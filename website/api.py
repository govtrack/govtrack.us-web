from django.conf import settings

from twostream.decorators import anonymous_view
from simplegetapi.views import do_api_call, build_api_documentation

from bill.models import Bill, Cosponsor
from person.models import Person, PersonRole
from vote.models import Vote, Voter
from committee.models import Committee, CommitteeMember

def get_apiv2_model_qs(model):
	from django.http import Http404
	
	def get_haystack_query_set(model, connection):
		from haystack.query import SearchQuerySet
		return SearchQuerySet().using(connection).filter(indexed_model_name__in=[model.__name__])
	
	if model == "bill":
		model = Bill
		qs = get_haystack_query_set(model, "bill")
	elif model == "cosponsorship":
		model = Cosponsor
		qs = Cosponsor.objects.all()
	elif model == "person":
		model = Person
		qs = get_haystack_query_set(model, "person")
	elif model == "role":
		model = PersonRole
		qs = PersonRole.objects.all()
	elif model == "vote":
		model = Vote
		qs = Vote.objects.all()
	elif model in ("vote_voter", "voter"):
		model = Voter
		qs = Voter.objects.all()
	elif model in ("committee"):
		from committee.models import Committee
		model = Committee
		qs = Committee.objects.all()
	elif model in ("committee_member"):
		from committee.models import CommitteeMember
		model = CommitteeMember
		qs = CommitteeMember.objects.all()
	else:
		raise Http404()
		
	return model, qs

@anonymous_view	
def apiv2(request, model, id):
	model, qs = get_apiv2_model_qs(model)
	return do_api_call(request, model, qs, id)
	
from django.shortcuts import render

def api_overview(request):
	baseurl = "https://%s/api/v2/" % request.META["HTTP_HOST"]
	
	endpoints = ("bill", "cosponsorship", "person", "role", "vote", "vote_voter", "committee", "committee_member")
	
	api = [ (model, build_api_documentation(*get_apiv2_model_qs(model))) for model in endpoints ]
	
	return render(request, 'website/developers/api.html', {
		"baseurl": baseurl,
		"api": api,
		})



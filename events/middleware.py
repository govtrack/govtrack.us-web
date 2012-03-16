from models import SubscriptionList

def template_context_processor(request):
	context = { }
	
	if request.user.is_authenticated():
		subfeeds = set()
		for x in SubscriptionList.objects.filter(user=request.user):
			subfeeds |= set(x.trackers.all())
		context["subscription_feeds"] = subfeeds
	
	return context


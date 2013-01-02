from django.conf import settings

class CacheLogic:
	def __init__(self):
		if settings.SESSION_SAVE_EVERY_REQUEST:
			raise Exception("You must set SESSION_SAVE_EVERY_REQUEST to False in order to use twostream.middleware.CacheLogic.")
		
	def process_response(self, request, response):
		if not getattr(request, "anonymous", False)\
			or request.method not in ("GET", "HEAD"):
			# This view does not have the anonymous attribute, or was requested
			# with a method we should not cache, so apply cache-control headers
			# to prevent any upstream caching.
			response['Pragma'] = 'no-cache'
			response["Cache-Control"] = "no-cache, no-store, must-revalidate"
			
		return response
		

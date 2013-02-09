# Make pages more cachable by splitting user-specific parts of
# a page from anonymous parts.

from functools import wraps

from django.contrib.auth.models import AnonymousUser
from django.views.decorators.cache import cache_control
import django.middleware.csrf

# Inject ourselves into CSRF processing to prevent the generation of CSRF
# tokens on anonymous views.
old_csrf_get_token = django.middleware.csrf.get_token
def new_csrf_get_token(request):
	if getattr(request, "anonymous", False):
		raise Exception("Requests marked 'anonymous' cannot generate CSRF tokens!")
	return old_csrf_get_token(request)
django.middleware.csrf.get_token = new_csrf_get_token

def anonymous_view(view):
	"""Marks a view as an anonymous, meaning this view returns nothing specific
	to the logged in user. In order to enforce this, the user, session, and COOKIES
	attributes of the request are cleared along with some keys in META.
	Additionally it sets cache-control settings on the output of the page and sets
	request.anonymous = True, which can be used in templates."""
	view = cache_control(public=True)(view)
	@wraps(view)
	def g(request, *args, **kwargs):
		request.anonymous = True
		request.COOKIES = { }
		request.user = AnonymousUser()
		if hasattr(request, "session"): request.session = { }
		for header in list(request.META.keys()):
			if header not in ('CONTENT_LENGTH', 'CONTENT_TYPE', 'HTTP_HOST', 'QUERY_STRING', 'REQUEST_METHOD', 'SERVER_NAME', 'SERVER_PORT'):
				del request.META[header]
		response = view(request, *args, **kwargs)
		response.csrf_processing_done = True # prevent generation of CSRF cookies
		return response
	return g
		
def user_view_for(anon_view_func):
	"""Marks a view as providing user-specific information for a view that the
	anonymous_view decorator has been applied to."""
	def decorator(view):
		anon_view_func.user_func = view
		return view
	return decorator


from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe

import registration.providers

register = template.Library()

def get_providers(filter=lambda p : True):
	providers = [p for p in registration.providers.providers.keys() if filter(registration.providers.providers[p])]
	providers.sort(key = lambda p : registration.providers.providers[p]["sort_order"] if "sort_order" in registration.providers.providers[p] else 1000)
	return providers

@register.filter
@stringfilter
def all_providers(value):
	return get_providers()

@register.filter
@stringfilter
def new_account_providers(value):
	return get_providers(filter = lambda p : "login" not in p or p["login"])

@register.filter
@stringfilter
def provider_name(value):
	return registration.providers.providers[value]["displayname"]

@register.filter
@stringfilter
def provider_logo(value, size):
	if not "logo_urls" in registration.providers.providers[value]:
		return ""
	url = ""
	for logosize, logourl in registration.providers.providers[value]["logo_urls"]:
		if logosize <= size:
			url = logourl
	return url


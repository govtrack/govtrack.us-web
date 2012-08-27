from django import template
import random

register = template.Library()

@register.simple_tag
def randint(a, b):
	return random.randint(int(a), int(b))

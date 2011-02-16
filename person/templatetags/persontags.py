from django import template

from person.types import Gender

register = template.Library()

@register.filter
def hisher(person):
	if person.gender == Gender.male:
		return "his"
	else:
		return "her"


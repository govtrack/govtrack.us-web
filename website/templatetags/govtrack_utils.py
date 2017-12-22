from django import template
from django.utils.translation import ugettext as _
from django.utils.encoding import force_unicode
from django.utils import safestring
from django.template.defaultfilters import stringfilter
import random, markdown2
import json as jsonlib

register = template.Library()

@register.assignment_tag
def randint(a, b):
	return random.randint(int(a), int(b))

@register.filter
def likerttext(value):
    likertdict = { -3: "Strongly oppose",
                   -2: "Moderately oppose",
                   -1: "Slightly oppose",
                    0: "Neither support nor oppose",
                    1: "Slightly support",
                    2: "Moderately support",
                    3: "Strongly support"}
    return likertdict.get(value)

@register.filter
def ordinalhtml(value):
    """
    Converts an integer to its ordinal as HTML. 1 is '1<sup>st</sup>',
    and so on.
    """
    try:
        value = int(value)
    except ValueError:
        return value
    t = (_('th'), _('st'), _('nd'), _('rd'), _('th'), _('th'), _('th'), _('th'), _('th'), _('th'))
    if value % 100 in (11, 12, 13): # special case
        return safestring.mark_safe(u"%d<sup>%s</sup>" % (value, t[0]))
    return safestring.mark_safe(u'%d<sup>%s</sup>' % (value, t[value % 10]))

@register.filter(is_safe=True)
@stringfilter
def markdown(value):
    return safestring.mark_safe(markdown2.markdown(force_unicode(value), safe_mode=True))

@register.filter(is_safe=True)
def json(value):
    return safestring.mark_safe(jsonlib.dumps(value))

@register.filter(is_safe=True)
@stringfilter
def stripfinalperiod(value):
    if value.endswith("."):
        value = value[:-1]
    return value

@register.filter
def mult(value, operand):
    return float(value) * float(operand)

@register.filter
def div(value, operand):
    return float(value) / float(operand)

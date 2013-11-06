from django import template
from django.utils.translation import ugettext as _
from django.utils.encoding import force_unicode
from django.utils import safestring
from django.template.defaultfilters import stringfilter
import random, markdown2

register = template.Library()

@register.assignment_tag
def randint(a, b):
	return random.randint(int(a), int(b))

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

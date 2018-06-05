from django import template
from django.utils.translation import ugettext as _
from django.utils.encoding import force_unicode
from django.utils import safestring
from django.template.defaultfilters import stringfilter
import random
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
        return safestring.mark_safe("%d<sup>%s</sup>" % (value, t[0]))
    return safestring.mark_safe('%d<sup>%s</sup>' % (value, t[value % 10]))

@register.filter(is_safe=True)
@stringfilter
def markdown(value):
    # Renders the string using CommonMark in safe mode, which blocks
    # raw HTML in the input and also some links using a blacklist,
    # plus a second pass filtering using a whitelist for allowed
    # tags and URL schemes.

    import CommonMark
    ast = CommonMark.Parser().parse(force_unicode(value))
    html = CommonMark.HtmlRenderer({ 'safe': True }).render(ast)

    import html5lib, urllib.parse
    def filter_url(url):
        try:
            urlp = urllib.parse.urlparse(url)
        except Exception as e:
            # invalid URL
            return None
        if urlp.scheme not in ("http", "https"):
            return None
        return url
    valid_tags = set('strong em a code p h1 h2 h3 h4 h5 h6 pre br hr img ul ol li span blockquote'.split())
    valid_tags = set('{http://www.w3.org/1999/xhtml}' + tag for tag in valid_tags)
    dom = html5lib.HTMLParser().parseFragment(html)
    for node in dom.iter():
        if node.tag not in valid_tags and node.tag != 'DOCUMENT_FRAGMENT':
            node.tag = '{http://www.w3.org/1999/xhtml}span'
        for name, val in node.attrib.items():
            if name.lower() in ("href", "src"):
                val = filter_url(val)
                if val is None:
                    node.attrib.pop(name)
                else:
                    node.set(name, val)
            else:
                # No other attributes are permitted.
                node.attrib.pop(name)
    html = html5lib.serialize(dom, quote_attr_values="always", omit_optional_tags=False, alphabetical_attributes=True)

    return safestring.mark_safe(html)

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


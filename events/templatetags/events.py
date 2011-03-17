from django import template
from django.template import Context, Template

register = template.Library()

@register.filter
def render_event(event, feed):
    meta = event.render(feeds=(feed,))
    meta["body_html"] = Template(meta["body_html_template"]).render(Context(meta["context"]))
    return meta



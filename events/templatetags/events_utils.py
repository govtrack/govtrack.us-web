from django import template
from django.template import Context, Template
from django.template.defaultfilters import stringfilter
from django.conf import settings

import events.models

register = template.Library()

@register.filter
def render_event(event, feed):
    if isinstance(event, dict):
        # values() returns the source_content_type's primary key rather than the object itself 
        from django.contrib.contenttypes.models import ContentType
        if type(event["source_content_type"]) != ContentType:
            event["source_content_type"] = ContentType.objects.get(id=event["source_content_type"])
        if "feeds" in event: # Event constructor can't take this arg
            event = dict(event)
            del event["feeds"]
        event = events.models.Event(**event)
        if not event.source: # database inconsistency
            return None
    
    if isinstance(feed, events.models.Feed):
        feeds = (feed,)
    elif feed == "":
        feeds = None
    else:
        feeds = feed
    meta = event.render(feeds=feeds)
    meta["guid"] = "%s:%d:%s" % (event.source_content_type, event.source_object_id, event.eventid)
    
    c = dict()
    c.update(meta["context"])
    c["SITE_ROOT"] = settings.SITE_ROOT_URL
    
    meta["body_html"] = Template(meta["body_html_template"]).render(Context(c))
    meta["body_text"] = Template(meta["body_text_template"]).render(Context(c))
    
    return meta

@register.filter
@stringfilter
def append_qsarg(value, arg):
    if not arg: return value
    if "?" in value:
        value += "&"
    else:
        value += "?"
    return value + unicode(arg)



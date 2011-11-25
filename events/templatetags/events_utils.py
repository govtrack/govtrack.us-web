from django import template
from django.template import Context, Template

import events.models

register = template.Library()

@register.filter
def render_event(event, feed):
    if isinstance(event, dict):
        # values() returns the source_content_type's primary key rather than the object itself 
        from django.contrib.contenttypes.models import ContentType
        event["source_content_type"] = ContentType.objects.get(id=event["source_content_type"])
        event = events.models.Event(**event)
    
    if isinstance(feed, events.models.Feed):
        feeds = (feed,)
    elif feed == "":
        feeds = None
    else:
        feeds = feed
    meta = event.render(feeds=feeds)
    meta["guid"] = "%s:%d:%s" % (event.source_content_type, event.source_object_id, event.eventid)
    meta["body_html"] = Template(meta["body_html_template"]).render(Context(meta["context"]))
    meta["body_text"] = Template(meta["body_text_template"]).render(Context(meta["context"]))
    
    return meta



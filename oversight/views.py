# -*- coding: utf-8 -*-
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.http import Http404
from django.conf import settings

from common.decorators import render_to
from twostream.decorators import anonymous_view, user_view_for  

from .models import OversightTopic

@anonymous_view
@render_to('oversight/oversight_list.html')
def oversight_topic_list(request):
    return {
        "topics": OversightTopic.objects.all().order_by('-created'),
    }

@user_view_for(oversight_topic_list)
def oversight_topic_list_user_view(request):
    from person.views import render_subscribe_inline
    ret = { }
    ret.update(render_subscribe_inline(request, OversightTopic.get_overview_feed()))
    return ret

@anonymous_view
@render_to('oversight/oversight_details.html')
def oversight_topic_details(request, id, slug):
    topic = get_object_or_404(OversightTopic, id=id)

    # redirect to canonical URL
    if request.path != topic.get_absolute_url():
        return redirect(topic.get_absolute_url(), permanent=True)

    return {
        "topic": topic,
        "feed": topic.get_feed(),
    }

@user_view_for(oversight_topic_details)
def oversight_topic_details_user_view(request, id, slug):
    from person.views import render_subscribe_inline
    topic = get_object_or_404(OversightTopic, id=id)
    ret = { }
    ret.update(render_subscribe_inline(request, topic.get_feed()))
    return ret
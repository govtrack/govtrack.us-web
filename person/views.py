# -*- coding: utf-8 -*-
import os
from datetime import datetime, timedelta

from django.shortcuts import redirect, get_object_or_404
from django.core.urlresolvers import reverse

from common.decorators import render_to
from common.pagination import paginate

from person.models import Person, PersonRole
from person import analysis
from person.video import get_youtube_videos, get_sunlightlabs_videos

@render_to('person/person_details.html')
def person_details(request, pk):
    person = get_object_or_404(Person, pk=pk)
    if request.path != person.get_absolute_url():
        return redirect(person.get_absolute_url(), permanent=True)
    role = person.get_current_role()
    if role:
        active_role = True
    else:
        active_role = False
        try:
            role = person.roles.order_by('-enddate')[0]
        except PersonRole.DoesNotExist:
            role = None

    photo_path = 'data/photos/%d-100px.jpeg' % person.pk
    if os.path.exists(photo_path):
        photo = '/' + photo_path
    else:
        photo = None

    analysis_data = analysis.load_data(person)

    videos = []

    if person.youtubeid:
        yt_videos = get_youtube_videos(person.youtubeid)
        videos.extend(yt_videos['videos'])

    if person.bioguideid:
        sunlight_videos = get_sunlightlabs_videos(person.bioguideid)
        videos.extend(sunlight_videos['videos'])

    recent_video = None
    if videos:
        videos.sort(key=lambda x: x['published'], reverse=True)
        if videos[0]['published'] > datetime.now() - timedelta(days=10):
            recent_video = videos[0]
            videos = videos[1:]

    # We are intrested only in five videos
    videos = videos[:4]

    return {'person': person,
            'role': role,
            'active_role': active_role,
            'photo': photo,
            'analysis_data': analysis_data,
            'recent_video': recent_video,
            'videos': videos,
            }


@render_to('person/person_list.html')
def person_list(request):
    page = paginate(Person.objects.all(), request)
    return {'page': page,
            }


# -*- coding: utf-8 -*-
from django.shortcuts import redirect, get_object_or_404
from django.core.urlresolvers import reverse

from common.decorators import render_to
from common.pagination import paginate

from vote.models import Vote, CongressChamber
from vote.forms import VoteFilterForm
from person.util import load_roles_at_date

@render_to('vote/vote_list.html')
def vote_list(request):
    qs = Vote.objects.order_by('-created')
    if 'year' in request.GET:
        form = VoteFilterForm(request.GET)
    else:
        form = VoteFilterForm()
    if form.is_valid():
        qs = form.filter(qs)
    page = paginate(qs, request, per_page=50)
    recent_vote = Vote.objects.order_by('-created')[0]
    return {'page': page,
            'form': form,
            'recent_vote': recent_vote,
            }


@render_to('vote/vote_details.html')
def vote_details(request, congress, session, chamber_code, number):
    if chamber_code == 'h':
        chamber = CongressChamber.house
    else:
        chamber = CongressChamber.senate
    vote = get_object_or_404(Vote, congress=congress, session=session,
                             chamber=chamber, number=number)
    voters = list(vote.voters.all().select_related('person', 'option'))
    load_roles_at_date([x.person for x in voters], vote.created)
    return {'vote': vote,
            'voters': voters,
            'CongressChamber': CongressChamber,
            }

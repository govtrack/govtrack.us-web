# -*- coding: utf-8 -*-
import csv
from StringIO import StringIO

from django.shortcuts import redirect, get_object_or_404
from django.core.urlresolvers import reverse
from django.http import HttpResponse

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


def load_vote(congress, session, chamber_code, number):
    """
    Helper utility to get `Vote` instance by arguments
    provided in the request.
    """

    if chamber_code == 'h':
        chamber = CongressChamber.house
    else:
        chamber = CongressChamber.senate
    return get_object_or_404(Vote, congress=congress, session=session,
                             chamber=chamber, number=number)


@render_to('vote/vote_details.html')
def vote_details(request, congress, session, chamber_code, number):
    vote = load_vote(congress, session, chamber_code, number)
    voters = list(vote.voters.all().select_related('person', 'option'))
    load_roles_at_date([x.person for x in voters], vote.created)
    return {'vote': vote,
            'voters': voters,
            'CongressChamber': CongressChamber,
            }


def vote_export_csv(request, congress, session, chamber_code, number):
    vote = load_vote(congress, session, chamber_code, number)
    voters = vote.voters.all().select_related('person', 'option')
    load_roles_at_date([x.person for x in voters], vote.created)

    outfile = StringIO()
    writer = csv.writer(outfile)
    for voter in voters:
        writer.writerow([voter.person.pk, voter.person.role.state, voter.person.role.district,
                         voter.option.value, voter.person.name_no_district().encode('utf-8')])
    output = outfile.getvalue()
    firstline = '%s Vote #%d %s - %s\n' % (vote.get_chamber_display(), vote.number,
                                         vote.created.strftime('%b %d, %Y'), vote.question)
    firstline = firstline.encode('utf-8')
    return HttpResponse(firstline + output, content_type='text/csv')


def vote_export_xml(request, congress, session, chamber_code, number):
    vote = load_vote(congress, session, chamber_code, number)
    fobj = open('data/us/%s/rolls/%s%s-%s.xml' % (congress, chamber_code, session, number))
    return HttpResponse(fobj, content_type='text/xml')

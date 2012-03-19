# -*- coding: utf-8 -*-
import csv
from StringIO import StringIO
from datetime import datetime

from django.http import HttpResponse
from django.shortcuts import redirect, get_object_or_404, render_to_response
from django.template import RequestContext
from django.core.urlresolvers import reverse

from common.decorators import render_to

from numpy import median

from vote.models import Vote, CongressChamber, VoterType, VoteCategory
from vote.search import vote_search_manager
from person.util import load_roles_at_date
from us import get_all_sessions

ideology_scores = { }

def vote_list(request):
    return vote_search_manager().view(request, "vote/vote_list.html",
        defaults = { "session": len(get_all_sessions())-1 },
        paginate = lambda form : "session" not in form ) # people like to see all votes for a year on one page

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
    load_roles_at_date([x.person for x in voters if x.person != None], vote.created)
    
    # sorting by party actually sorts by party first and by ideology score
    # second.
    global ideology_scores
    if not congress in ideology_scores:
        ideology_scores[congress] = { }
        for ch in ('h', 's'):
            try:
                for ideolog in csv.reader(open("data/us/%d/stats/sponsorshipanalysis_%s.txt" % (int(congress), ch))):
                    if ideolog[0] == "ID": continue # header row
                    ideology_scores[congress][int(ideolog[0])] = float(ideolog[1])
                ideology_scores[congress]["MEDIAN"] = median(ideology_scores[congress].values())
            except IOError:
                ideology_scores[congress] = None
    
    if ideology_scores[congress]:
        for voter in voters:
            voter.ideolog_score = ideology_scores[congress].get(voter.person.id, ideology_scores[congress]["MEDIAN"])
        
    voters.sort(key = lambda x : (x.option.key, x.person.role.party if x.person and x.person.role else "", x.person.name_no_details_lastfirst if x.person else x.get_voter_type_display()))
    
    return {'vote': vote,
            'voters': voters,
            'CongressChamber': CongressChamber,
            "VoterType": VoterType,
            "VoteCategory": VoteCategory._items,
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
                                         vote.created.isoformat(), vote.question) # strftime doesn't work on dates before 1900
    firstline = firstline.encode('utf-8')
    r = HttpResponse(firstline + output, content_type='text/csv')
    r['Content-Disposition'] = 'attachment; filename=' + vote.get_absolute_url()[1:].replace("/", "_") + ".csv"
    return r


def vote_export_xml(request, congress, session, chamber_code, number):
    vote = load_vote(congress, session, chamber_code, number)
    fobj = open('data/us/%s/rolls/%s%s-%s.xml' % (congress, chamber_code, session, number))
    return HttpResponse(fobj, content_type='text/xml')

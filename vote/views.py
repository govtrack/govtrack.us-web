# -*- coding: utf-8 -*-
import csv
from StringIO import StringIO
from datetime import datetime

from django.http import HttpResponse, Http404
from django.shortcuts import redirect, get_object_or_404, render_to_response
from django.template import RequestContext
from django.core.urlresolvers import reverse
from django.views.decorators.cache import cache_page

from common.decorators import render_to

from numpy import median

from vote.models import Vote, CongressChamber, VoterType, VoteCategory
from vote.search import vote_search_manager
from person.util import load_roles_at_date
from us import get_all_sessions

from twostream.decorators import anonymous_view

from settings import CURRENT_CONGRESS

ideology_scores = { }

def vote_list(request):
    # Get the default session to show. We may have sessions listed that are
    # in the future, during a transition, so take the most recent that at
    # least has started.
    default_session = None
    for i, (cn, sn, sd, ed) in enumerate(get_all_sessions()):
        if sd > datetime.now().date(): break
        default_session = i
    
    return vote_search_manager().view(request, "vote/vote_list.html",
        defaults = { "session": default_session },
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
            voter.ideolog_score = ideology_scores[congress].get(voter.person.id if voter.person else 0, ideology_scores[congress]["MEDIAN"])
        
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
    load_roles_at_date([x.person for x in voters if x.person], vote.created)

    outfile = StringIO()
    writer = csv.writer(outfile)
    for voter in voters:
        writer.writerow([
            voter.person.pk if voter.person else "--",
            voter.person.role.state if voter.person and voter.person.role else "--",
            voter.person.role.district if voter.person and voter.person.role else "--",
            voter.option.value,
            voter.person.name_no_district().encode('utf-8') if voter.person else voter.get_voter_type_display(),
            voter.person.role.party if voter.person and voter.person.role else "--",])
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
    
@anonymous_view
@cache_page(60 * 60 * 6)
def vote_thumbnail_image(request, congress, session, chamber_code, number):
	vote = load_vote(congress, session, chamber_code, number)
	
	import cairo, re
	from StringIO import StringIO
	
	font_face = "DejaVu Serif Condensed"
	image_width = 300
	image_height = 250
	
	vote_title = vote.question
	vote_result_2 = re.sub("^(Bill|Amendment|Resolution|Conference Report) ", "", vote.result)
	vote_citation = vote.get_chamber_display() + " Vote #" + str(vote.number) + " -- " + vote.created.strftime("%x")
	seating_rows = 8 if vote.chamber == CongressChamber.house else 4
		# 4 for Senate (http://www.senate.gov/artandhistory/art/special/Desks/chambermap.cfm)
		# about 8 for the House
		
	totals = vote.totals()
	total_counts = { }
	yea_counts_by_party = [0,0] # D, R
	party_members_total = [0,0] # D, R
	for opt in totals["options"]:
		total_counts[opt["option"].key] = opt["count"]
		for i in xrange(len(totals["parties"])):
			if totals["parties"][i] not in ("Democrat", "Republican"): continue
			j = 0 if totals["parties"][i] == "Democrat" else 1
			party_members_total[j] += opt["party_counts"][i]["count"]
			if opt["option"].key == "+": yea_counts_by_party[j] += opt["party_counts"][i]["count"]
	if "+" not in total_counts or "-" not in total_counts: raise Http404() # no thumbnail for other sorts of votes
	vote_result_1 = "%d-%d" % (total_counts["+"], total_counts["-"])
	
	def show_text_centered(ctx, text, max_width=None):
		while True:
			(x_bearing, y_bearing, width, height, x_advance, y_advance) = ctx.text_extents(text)
			if max_width is not None and width > max_width:
				text2 = re.sub(r" \S+(\.\.\.)?$", "...", text)
				if text2 != text:
					text = text2
					continue
			break
			
		ctx.rel_move_to(-width/2, height)
		ctx.show_text(text)
	
	im = cairo.ImageSurface(cairo.FORMAT_ARGB32, image_width, image_height)
	ctx = cairo.Context(im)
	
	ctx.select_font_face(font_face, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
	
	# clear background
	ctx.set_source_rgb(1,1,1)
	ctx.new_path()
	ctx.line_to(0, 0)
	ctx.line_to(image_width, 0)
	ctx.line_to(image_width, image_height)
	ctx.line_to(0, image_height)
	ctx.fill()
	
	ctx.set_source_rgb(0,1,0)
	ctx.set_line_width(10)
	ctx.new_path()
	ctx.line_to(0, 0)
	ctx.line_to(image_width, image_height)
	#ctx.stroke()
	
	# Title
	ctx.set_font_size(20)
	ctx.set_source_rgb(.2,.2,.2)
	ctx.move_to(150,10)
	show_text_centered(ctx, vote_title, max_width=.95*image_width) 
	
	# Vote Tally
	ctx.set_font_size(26)
	ctx.set_source_rgb(.1, .1, .1)
	ctx.move_to(150,50)
	show_text_centered(ctx, vote_result_1)
	
	# Vote Result
	ctx.move_to(150,88)
	show_text_centered(ctx, vote_result_2) 
	w = max(ctx.text_extents(vote_result_1)[2], ctx.text_extents(vote_result_2)[2])
	
	# Line
	ctx.set_line_width(1)
	ctx.new_path()
	ctx.line_to(150-w/2, 82)
	ctx.rel_line_to(w, 0)
	ctx.stroke()
	
	# Vote Info
	ctx.select_font_face(font_face, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
	ctx.set_font_size(14)
	ctx.move_to(150,image_height-25)
	show_text_centered(ctx, vote_citation, max_width=.98*image_width) 
	
	# Seats
	seats_per_row = 18
	inner_r = w/2 * 1.5
	if seating_rows == 4: inner_r = max(inner_r, 75)
	outer_r = image_width * .45
	seat_size = min(.8 * (outer_r-inner_r) / seating_rows, .35 * (2*3.14159*inner_r) / seats_per_row)
	for seat_row in xrange(seating_rows):
		r = inner_r + (outer_r-inner_r) * seat_row / float(seating_rows-1)
		n_seats = int(seats_per_row * r/inner_r + .5)
		for seat_pos in xrange(n_seats):
			# which party is this seat and how should we color it?
			if (n_seats-seat_pos-1)*(party_members_total[0]+party_members_total[1]) < yea_counts_by_party[0]*n_seats:
				# D-yea
				ctx.set_source_rgb(0.05, 0.24, 0.63)
			elif (n_seats-seat_pos-1)*(party_members_total[0]+party_members_total[1]) < party_members_total[0]*n_seats:
				# D-nay
				ctx.set_source_rgb(0.85, 0.85, 1.0)
			elif seat_pos*(party_members_total[0]+party_members_total[1]) < yea_counts_by_party[1]*n_seats:
				# R-yea
				ctx.set_source_rgb(0.90, 0.05, 0.07)
			else:
				# R-nay
				ctx.set_source_rgb(1.0, 0.85, 0.85)
			
			# draw the seat
			ctx.identity_matrix()
			ctx.translate(image_width/2, 75)
			ctx.rotate(3.14159 * seat_pos/float(n_seats-1))
			ctx.translate(r, 0)
			ctx.rectangle(-seat_size/2, -seat_size/2, seat_size, seat_size)
			ctx.fill()
	
	# Convert the image buffer to raw bytes.
	buf = StringIO()
	im.write_to_png(buf)
	v = buf.getvalue()
	
	# Form the response.
	r = HttpResponse(v, content_type='image/png')
	r["Content-Length"] = len(v)
	return r
	
import django.contrib.sitemaps
class sitemap_current(django.contrib.sitemaps.Sitemap):
    changefreq = "yearly"
    priority = 1.0
    def items(self):
        return Vote.objects.filter(congress=CURRENT_CONGRESS)
class sitemap_previous(django.contrib.sitemaps.Sitemap):
    changefreq = "yearly"
    priority = 0.25
    def items(self):
        return Vote.objects.filter(congress=CURRENT_CONGRESS-1)
class sitemap_archive(django.contrib.sitemaps.Sitemap):
    changefreq = "yearly"
    priority = 0.25
    def items(self):
        return Vote.objects.filter(congress__lt=CURRENT_CONGRESS-1)
    

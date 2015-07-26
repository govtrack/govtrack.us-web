# -*- coding: utf-8 -*-
import csv
from StringIO import StringIO
from datetime import datetime

from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render_to_response
from django.template import RequestContext
from django.core.urlresolvers import reverse
from django.views.decorators.cache import cache_page

from common.decorators import render_to

from numpy import median

from vote.models import Vote, CongressChamber, VoterType, VoteCategory, VoteSummary
from vote.search import vote_search_manager
from events.models import Feed
from person.util import load_roles_at_date
from us import get_all_sessions

from twostream.decorators import anonymous_view, user_view_for

from settings import CURRENT_CONGRESS

ideology_scores = { }

@anonymous_view
def vote_list(request):
    # Get the default session to show. We may have sessions listed that are
    # in the future, during a transition, so take the most recent that at
    # least has started.
    default_session = None
    for i, (cn, sn, sd, ed) in reversed(list(enumerate(get_all_sessions()))):
        if sd > datetime.now().date(): continue
        if not Vote.objects.filter(congress=cn, session=sn).exists(): continue
        default_session = i
        break
    
    return vote_search_manager().view(request, "vote/vote_list.html",
        defaults = { "session": default_session,
					 "sort": request.GET.get("sort",None)},
        paginate = lambda form : "session" not in form, # people like to see all votes for a year on one page
        context = { "feed": Feed(feedname="misc:allvotes") })

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

@anonymous_view
@render_to('vote/vote_details.html')
def vote_details(request, congress, session, chamber_code, number):
    vote = load_vote(congress, session, chamber_code, number)
    voters = list(vote.voters.all().select_related('person', 'option'))
    load_roles_at_date([x.person for x in voters if x.person != None], vote.created)
    
    # load the role for the VP, since load_roles_at_date only loads
    # MoC roles
    has_vp_vote = False
    for voter in voters:
        if voter.voter_type == VoterType.vice_president:
            from person.types import RoleType
            has_vp_vote = True
            try:
                voter.person.role = voter.person.roles.get(role_type=RoleType.vicepresident, startdate__lte=vote.created, enddate__gte=vote.created)
            except:
                raise
                pass # wahtever
    
    # Test if we have a diagram for this vote. The only
    # way to test is to try to make it.
    try:
        vote_thumbnail_image(request, congress, session, chamber_code, number, "diagram")
        has_diagram = True
    except Http404:
        has_diagram = False
    
    # sorting by party actually sorts by party first and by ideology score
    # second.
    has_ideology_scores = False
    congress = int(congress)
    global ideology_scores
    load_ideology_scores(congress)
    if ideology_scores[congress]:
        for voter in voters:
            if voter.person and voter.person.id in ideology_scores[congress]:
                voter.ideolog_score = ideology_scores[congress][voter.person.id]
                has_ideology_scores = True
            else:
                voter.ideolog_score = \
            	ideology_scores[congress].get("MEDIAN:" + (voter.person.role.party if voter.person and voter.person.role else ""),
            		ideology_scores[congress]["MEDIAN"])
        
    # perform an initial sort for display
    voters.sort(key = lambda x : (x.option.key, x.person.role.party if x.person and x.person.role else "", x.person.name_no_details_lastfirst if x.person else x.get_voter_type_display()))

    # did any Senate leaders switch their vote for a motion to reconsider?
    reconsiderers = vote.possible_reconsideration_votes(voters)
    reconsiderers_titles = "/".join(v.person.role.leadership_title for v in reconsiderers)

    # compute statistical outliers (this marks the Voter instances with an is_outlier attribute)
    get_vote_outliers(voters)
    
    return {'vote': vote,
            'voters': voters,
            'CongressChamber': CongressChamber,
            "VoterType": VoterType,
            "VoteCategory": VoteCategory._items,
            'has_vp_vote': has_vp_vote,
            'has_diagram': has_diagram,
            'has_ideology_scores': has_ideology_scores,
            'reconsiderers': (reconsiderers, reconsiderers_titles),
            }

@user_view_for(vote_details)
def vote_details_userview(request, congress, session, chamber_code, number):
    ret = { }

    if request.user.is_staff:
        vote = load_vote(congress, session, chamber_code, number)
        admin_panel = """
            <div class="clear"> </div>
            <div style="margin-top: 1.5em; padding: .5em; background-color: #EEE; ">
                <b>ADMIN</b> - <a href="{% url "vote_go_to_summary_admin" %}?vote={{vote.id}}">Edit Summary</a>
            </div>
            """

        from django.template import Template, Context, RequestContext, loader
        ret["admin_panel"] = Template(admin_panel).render(RequestContext(request, {
            'vote': vote,
            }))

    return ret

from django.contrib.auth.decorators import permission_required
@permission_required('vote.change_votesummary')
def go_to_summary_admin(request):
    summary, is_new = VoteSummary.objects.get_or_create(vote=get_object_or_404(Vote, id=request.GET["vote"]))
    return HttpResponseRedirect("/admin/vote/votesummary/%d" % summary.id)

def load_ideology_scores(congress):
    global ideology_scores
    if congress in ideology_scores: return
    ideology_scores[congress] = { }
    for ch in ('h', 's'):
        try:
            scores_by_party = { }
            for ideolog in csv.reader(open("data/us/%d/stats/sponsorshipanalysis_%s.txt" % (congress, ch))):
                if ideolog[0] == "ID": continue # header row
                if float(ideolog[2]) <  .1: continue # very low leadership score, ideology is not reliable
                ideology_scores[congress][int(ideolog[0])] = float(ideolog[1])
                scores_by_party.setdefault(ideolog[4].strip(), []).append(float(ideolog[1]))
            ideology_scores[congress]["MEDIAN"] = median(ideology_scores[congress].values())
            for party in scores_by_party:
                ideology_scores[congress]["MEDIAN:"+party] = median(scores_by_party[party])
        except IOError:
            ideology_scores[congress] = None

def get_vote_outliers(voters):
	# Run a really simple statistical model to see which voters don't
	# match predicted outcomes.

	import numpy
	from logistic_regression import logistic_regression, calcprob

	# Build a binary matrix of predictors.
	predictor_names = ('party', 'ideolog_score')
	party_values = { "Democrat": -1, "Republican": 1 }
	vote_values = { "+": 1, "-": 0 }
	x = [ [] for predictor in predictor_names ]
	y = [ ]
	for voter in voters:
		x[0].append(party_values.get(voter.person.role.party if voter.person and voter.person.role else None, 0)) # independents and unrecognized parties get 0
		x[1].append(getattr(voter, 'ideolog_score', 0)) # ideology scores may not be available in a Congress, also not available for vice president
		y.append(vote_values.get(voter.option.key, .5)) # present, not voting, etc => .5
	x = numpy.array(x)
	y = numpy.array(y)

	# Perform regression.
	try:
		regression_beta, J_bar, l = logistic_regression(x, y)
	except ValueError:
		# Something went wrong. No outliers will be reported.
		return

	# Predict votes.
	estimate = calcprob(regression_beta, x)/100.0

	# Mark voters whose vote is far from the prediction.
	for i, v in enumerate(voters):
		v.is_outlier = (abs(y[i]-estimate[i]) > .7)

@anonymous_view
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


@anonymous_view
def vote_export_xml(request, congress, session, chamber_code, number):
    vote = load_vote(congress, session, chamber_code, number)
    fobj = open('data/us/%s/rolls/%s%s-%s.xml' % (congress, chamber_code, session, number))
    return HttpResponse(fobj, content_type='text/xml')

@anonymous_view
def vote_get_json(request, congress, session, chamber_code, number):
    vote = load_vote(congress, session, chamber_code, number)
    return HttpResponseRedirect("/api/v2/vote/%d" % vote.id)
    
@anonymous_view
@cache_page(60 * 60 * 6)
def vote_thumbnail_image(request, congress, session, chamber_code, number, image_type):
	vote = load_vote(congress, session, chamber_code, number)
	
	import cairo, re, math
	from StringIO import StringIO
	
	# general image properties
	font_face = "DejaVu Serif Condensed"
	image_width = 300
	image_height = 250 if image_type == "thumbnail" else 170
	
	# format text to print on the image
	vote_title = re.sub(r"^On the Motion to ", "To ", vote.question)
	if re.match(r"Cloture .*Rejected", vote.result):
		vote_result_2 = "Filibustered"
	elif re.match(r"Cloture .*Agreed to", vote.result):
		vote_result_2 = "Proceed"
	else:
		vote_result_2 = re.sub("^(Bill|Amendment|Resolution|Conference Report|Nomination|Motion|Motion to \S+) ", "", vote.result)
	if vote_result_2 == "unknown": vote_result_2 = ""
	vote_date = vote.created.strftime("%x") if vote.created.year > 1900 else vote.created.isoformat().split("T")[0]
	vote_citation = vote.get_chamber_display() + " Vote #" + str(vote.number) + " -- " + vote_date
	
	# get vote totals by option and by party
	totals = vote.totals()
	total_count = 0
	total_counts = { } # key: total ({ "+": 123 }, etc.)
	yea_counts_by_party = [0,0,0] # D, I, R (+ votes totals)
	nay_counts_by_party = [0,0,0] # D, I, R (+/- votes totals)
	nonvoting_members_totals = [0,0,0] # D, I, R
	party_index = { "Democrat": 0, "Republican": 2 }
	for opt in totals["options"]:
		total_counts[opt["option"].key] = opt["count"]
		for i in xrange(len(totals["parties"])):
			j = party_index.get(totals["parties"][i], 1)
			if opt["option"].key not in ("+", "-"):
				# most votes are by proportion of those voting (not some cloture etc.),
				# so put present/not-voting tallies in a separate group
				nonvoting_members_totals[j] += opt["party_counts"][i]["count"]
				continue 
			total_count += opt["party_counts"][i]["count"]
			if opt["option"].key == "+":
				yea_counts_by_party[j] += opt["party_counts"][i]["count"]
			else:
				nay_counts_by_party[j] += opt["party_counts"][i]["count"]
	if total_count == 0 or "+" not in total_counts or "-" not in total_counts: raise Http404() # no thumbnail for other sorts of votes
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
	
	chart_top = 0
	if image_type == "thumbnail":
		# Title
		ctx.set_font_size(20)
		ctx.set_source_rgb(.2,.2,.2)
		ctx.move_to(150,10)
		show_text_centered(ctx, vote_title, max_width=.95*image_width)
		chart_top = 50
	
	# Vote Tally
	font_size = 26 if len(vote_result_2) < 10 else 22
	ctx.set_font_size(font_size)
	ctx.set_source_rgb(.1, .1, .1)
	ctx.move_to(150,chart_top)
	show_text_centered(ctx, vote_result_1)
	
	# Vote Result
	ctx.move_to(150,chart_top+12+font_size)
	show_text_centered(ctx, vote_result_2) 
	w = max(ctx.text_extents(vote_result_1)[2], ctx.text_extents(vote_result_2)[2])
	
	# Line
	ctx.set_line_width(1)
	ctx.new_path()
	ctx.line_to(150-w/2, chart_top+5+font_size)
	ctx.rel_line_to(w, 0)
	ctx.stroke()
	
	if image_type == "thumbnail":
		# Vote Chamber/Date/Number
		ctx.select_font_face(font_face, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
		ctx.set_font_size(14)
		ctx.move_to(150,image_height-25)
		show_text_centered(ctx, vote_citation, max_width=.98*image_width) 
	
	# Seats
	
	# Construct an array of rows of seats, where each entry maps to a particular
	# voter.
	
	# How many rows of seats? That is hard coded by chamber.
	seating_rows = 8 if vote.chamber == CongressChamber.house else 4
		# 4 for Senate (http://www.senate.gov/artandhistory/art/special/Desks/chambermap.cfm)
		# about 8 for the House
		
	# Long ago Congress had very few people.
	seating_rows = min(total_count, total_count / 8 + 1, seating_rows)
		
	# Determine the seating chart dimensions: the radius of the inside row of
	# seats and the radius of the outside row of seats.
	inner_r = w/2 * 1.25 + 5 # wrap closely around the text in the middle
	if seating_rows <= 4: inner_r = max(inner_r, 75) # don't make the inner radius too small
	outer_r = image_width * .45 # end close to the image width
	
	# If we assume the absolute spacing of seats is constant from row to row, then
	# the number of seats per row grows linearly with the radius, following the
	# circumference. If s0 is the number of seats on the inner row, then
	# floor(s0 * outer_r/inner_r) is the number of seats on the outer row. The total
	# number of seats is found by the sum of the arithmetic sequence (n/2 * (a_1+a_n)):
	#  n = (seating_rows/2)*(s0 + s0*outer_r/inner_r)
	# We want exactly total_count seats, so solving for s0...
	seats_per_row = 2.0 * total_count / (seating_rows*(1.0 + outer_r/inner_r))

	# How wide to draw a seat?
	seat_size = min(.8 * (outer_r-inner_r) / seating_rows, .35 * (2*3.14159*inner_r) / seats_per_row)

	# Determine how many seats on each row.
	seats_so_far = 0
	rowcounts = []
	for row in xrange(seating_rows):
		# What's the radius of this row?
		if seating_rows > 1:
			r = inner_r + (outer_r-inner_r) * row / float(seating_rows-1)
		else:
			r = inner_r
		
		# How many seats should we put on this row?
		if row < seating_rows-1:
			# Start with seats_per_row on the inner row and grow linearly.
			# Round to an integer. Alternate rounding down and up.
			n_seats = seats_per_row * r/inner_r
			n_seats = int(math.floor(n_seats) if (row % 2 == 0) else math.ceil(n_seats))
		else:
			# On the outermost row, just put in how many left we need
			# so we always have exactly the right number of seats.
			n_seats = total_count - seats_so_far
		
		rowcounts.append(n_seats)
		seats_so_far += n_seats
		
	# Make a list of all of the seats as a list of tuples of the
	# form (rownum, seatnum) where seatnum is an index from the
	# left side.
	seats = []
	for row, count in enumerate(rowcounts):
		for i in xrange(count):
			seats.append( (row, i) )
			
	# Sort the seats in the order we will fill them from left to right,
	# bottom to top.
	seats.sort(key = lambda seat : (seat[1]/float(rowcounts[seat[0]]), -seat[0]) )
	
	# We can draw in two modes. In one mode, we don't care which actual
	# person corresponds to which seat. We just draw the groups of voters
	# in blocks. Or we can draw the actual people in seats we assign
	# according to their ideology score, from left to right.

    # See if we have ideology scores.
	voter_details = None
	if True:
		global ideology_scores
		load_ideology_scores(vote.congress)
		if ideology_scores[vote.congress]:
			voter_details = [ ]
			
			# Load the voters, getting their role at the time they voted.
			voters = list(vote.voters.all().select_related('person', 'option'))
			load_roles_at_date([x.person for x in voters if x.person != None], vote.created)
			
			# Store ideology scores
			for voter in voters:
				if voter.option.key not in ("+", "-"): continue
				party = party_index.get(voter.person.role.party if voter.person and voter.person.role else "Unknown", 1)
				option = 0 if voter.option.key == "+" else 1
				coord =  ideology_scores[vote.congress].get(voter.person.id if voter.person else "UNKNOWN",
					ideology_scores[vote.congress].get("MEDIAN:" + (voter.person.role.party if voter.person and voter.person.role else ""),
						ideology_scores[vote.congress]["MEDIAN"]))
				voter_details.append( (coord, (party, option)) )
				
			# Sort voters by party, then by ideology score, then by vote.
			voter_details.sort(key = lambda x : (x[1][0], x[0], x[1][1]))
			
			if len(voter_details) != len(seats):
				raise ValueError("Gotta check this.")
				voter_details = None # abort
			
	if not voter_details:
		# Just assign voters to seats in blocks.
		#
		# We're fill the seats from left to right different groups of voters:
		#   D+, D-, I+, I-, R-, R+
		# For each group, for each voter in the group, pop off a seat and
		# draw him in that seat.
	
		# for each group of voters...
		seat_idx = 0
		for (party, vote) in [ (0, 0), (0, 1), (1, 0), (1, 1), (2, 1), (2, 0) ]:
			# how many votes in this group?
			n_voters = (yea_counts_by_party if vote == 0 else nay_counts_by_party)[party]
			# for each voter...
			for i in xrange(n_voters):
				seats[seat_idx] = (seats[seat_idx], (party, vote)) 
				seat_idx += 1
	
	else:
		# Assign voters to seats in order.
		for i in xrange(len(voter_details)):
			seats[i] = (seats[i], voter_details[i][1])

	# Draw the seats.
	
	group_colors = {
		(0, 0): (0.05, 0.24, 0.63), # D+
		(0, 1): (0.85, 0.85, 1.0), # D-
		(1, 0): (0.07, 0.05, 0.07), # I+
		(1, 1): (0.85, 0.85, 0.85), # I-
		(2, 0): (0.90, 0.05, 0.07), # R+
		(2, 1): (1.0, 0.85, 0.85), # R-
	}
	
	for ((row, seat_pos), (party, vote)) in seats:	
		# radius of this row (again, code dup)
		if seating_rows > 1:
			r = inner_r + (outer_r-inner_r) * row / float(seating_rows-1)
		else:
			r = inner_r
		
		# draw
		ctx.set_source_rgb(*group_colors[(party, vote)])
		ctx.identity_matrix()
		ctx.translate(image_width/2, chart_top+25)
		ctx.rotate(3.14159 - 3.14159 * seat_pos/float(rowcounts[row]-1))
		ctx.translate(r, 0)
		ctx.rectangle(-seat_size/2, -seat_size/2, seat_size, seat_size)
		ctx.fill()

	# Convert the image buffer to raw PNG bytes.
	buf = StringIO()
	im.write_to_png(buf)
	v = buf.getvalue()
	
	# Form the response.
	r = HttpResponse(v, content_type='image/png')
	r["Content-Length"] = len(v)
	return r

@anonymous_view
def vote_check_thumbnails(request):
    votes = Vote.objects.filter(congress=CURRENT_CONGRESS)\
        .order_by("congress", "session", "chamber", "number")
    ret = ""
    for v in votes:
        ret += """<div><a href="%s"><img src="%s" style="border: 1px solid #777"/></a></div>\n""" % (v.get_absolute_url(), v.get_absolute_url() + "/thumbnail")
    return HttpResponse(ret, content_type='text/html')
	
import django.contrib.sitemaps
class sitemap_current(django.contrib.sitemaps.Sitemap):
    changefreq = "yearly"
    priority = 1.0
    def items(self):
        return Vote.objects.filter(congress=CURRENT_CONGRESS)
class sitemap_archive(django.contrib.sitemaps.Sitemap):
    index_levels = ['congress', 'session', 'chamber']
    changefreq = "yearly"
    priority = 0.25
    def items(self):
        return Vote.objects.filter(congress__lt=CURRENT_CONGRESS)

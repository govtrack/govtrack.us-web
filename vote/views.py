# -*- coding: utf-8 -*-
import csv
from io import StringIO
from datetime import datetime

from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.core.urlresolvers import reverse
from django.views.decorators.cache import cache_page

from common.decorators import render_to

from numpy import median

from vote.models import Vote, CongressChamber, VoterType, VoteCategory, VoteSummary
from vote.search import vote_search_manager
from person.views import http_rest_json
from events.models import Feed
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
    voters = vote.get_voters()

    # If this is a vote on passage, but it's not the final vote on passage in this
    # chamber, issue a warning.
    has_subsequent_vote = False
    if vote.related_bill and vote.category in (VoteCategory.passage, VoteCategory.passage_suspension) \
      and vote.related_bill.votes.filter(chamber=vote.chamber, category__in=(VoteCategory.passage, VoteCategory.passage_suspension)).order_by('-created').first() != vote:
      has_subsequent_vote = True
    
    # Test if we have diagrams for this vote. The only
    # way to test is to try to make it.
    has_diagram = { }
    for image_type in ("map", "diagram"):
        try:
            vote_thumbnail_image(request, congress, session, chamber_code, number, image_type)
            has_diagram[image_type] = True
        except Http404:
            has_diagram[image_type] = False
    
    # sorting by party actually sorts by party first and by ideology score
    # second.
    has_ideology_scores = attach_ideology_scores(voters, vote.congress)
        
    # perform an initial sort for display
    voters.sort(key = lambda x : (x.option.key, x.person_role.party if x.person and x.person_role else "", x.person.name_no_details_lastfirst if x.person else x.get_voter_type_display()))

    # did any Senate leaders switch their vote for a motion to reconsider?
    reconsiderers = vote.possible_reconsideration_votes(voters)
    reconsiderers_titles = "/".join(v.person_role.leadership_title for v in reconsiderers)

    # compute statistical outliers (this marks the Voter instances with an is_outlier attribute)
    get_vote_outliers(voters)

    # get Explanations from ProPublica for House votes and attach to voter instances
    propublica_url = None
    propublica_count = 0
    if vote.chamber == CongressChamber.house and vote.congress >= 110:
        # ProPublica data starts at the 110th Congress, and also be sure to only do 77th forward where
        # we know the session is an integer (the session/legislative year).
        propublica_url = "https://projects.propublica.org/explanations/votes/%d/%d" % (int(vote.session), vote.number)
        try:
            explanations = http_rest_json("https://projects.propublica.org/explanations/api/votes/%d/%d.json" % (int(vote.session), vote.number))
        except:
            # squash all errors
            explanations = { }
        propublica_count = explanations.get("vote", {}).get("total_explanations", 0)
        expl_map = { e["bioguide_id"]: e for e in explanations.get("vote", {}).get("explanations", []) }
        for voter in voters:
            voter.explanation = expl_map.get(voter.person.bioguideid)
    
    return {'vote': vote,
            'voters': voters,
            'CongressChamber': CongressChamber,
            "VoterType": VoterType,
            "VoteCategory": VoteCategory._items,
            'has_vp_vote': len([v for v in voters if v.voter_type == VoterType.vice_president]) > 0,
            'has_diagram': has_diagram,
            'has_ideology_scores': has_ideology_scores,
            'has_subsequent_vote': has_subsequent_vote,
            'diagram_key_colors': [ (k, "rgb(%d,%d,%d)" % tuple([c*256 for c in clr])) for k, clr in vote_diagram_colors.items() ],
            'reconsiderers': (reconsiderers, reconsiderers_titles),
            'propublica_url': propublica_url,
            'propublica_count': propublica_count,
            }

@user_view_for(vote_details)
def vote_details_userview(request, congress, session, chamber_code, number):
    ret = { }

    if request.user.is_staff:
        vote = load_vote(congress, session, chamber_code, number)
        admin_panel = """
            <div class="clear"> </div>
            <div style="margin-top: 1.5em; padding: .5em; background-color: #EEE; ">
                <b>ADMIN</b>
                - <a href="/admin/vote/vote/{{vote.id}}/change/">Edit Vote</a>
                - <a href="{% url "vote_go_to_summary_admin" %}?vote={{vote.id}}">Edit Summary</a>
            </div>
            """

        from django.template import Template, Context
        ret["admin_panel"] = Template(admin_panel).render(Context({
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

def attach_ideology_scores(voters, congress):
    global ideology_scores
    has_ideology_scores = False
    load_ideology_scores(congress)
    if ideology_scores[congress]:
        for voter in voters:
            if voter.person and voter.person.id in ideology_scores[congress]:
                voter.ideolog_score = ideology_scores[congress][voter.person.id]
                has_ideology_scores = True
            else:
                voter.ideolog_score = \
            	ideology_scores[congress].get("MEDIAN:" + (voter.person_role.party if voter.person and voter.person_role else ""),
            		ideology_scores[congress]["MEDIAN"])
    return has_ideology_scores

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
		x[0].append(party_values.get(voter.party, 0)) # independents and unrecognized parties get 0
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
    voters = vote.get_voters()

    outfile = StringIO()
    writer = csv.writer(outfile)
    writer.writerow(["person", "state", "district", "vote", "name", "party"])
    for voter in voters:
        if voter.person: voter.person.role = voter.person_role # for name formatting
        writer.writerow([
            voter.person.pk if voter.person else "--",
            voter.person_role.state if voter.person and voter.person_role else "--",
            voter.person_role.district if voter.person and voter.person_role else "--",
            voter.option.value,
            voter.person.name_no_district().encode('utf-8') if voter.person else voter.get_voter_type_display(),
            voter.person_role.party if voter.person and voter.person_role else "--",])
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
	if image_type == "map":
		# SVG map.
		return vote_thumbnail_image_map(vote)
	else:
		# Seating diagram.
		return vote_thumbnail_image_seating_diagram(vote, image_type == "thumbnail")

vote_diagram_colors = {
	("D", "+"): (0/255.0, 142/255.0, 209/255.0), # same as CSS color
	("D", "-"): (213/255.0, 244/255.0, 255/255.0), # reduced saturation and then matched lightness with R at 95
	("I", "+"): (0.07, 0.05, 0.07),
	("I", "-"): (0.85, 0.85, 0.85),
	("R", "+"): (248/255.0, 54/255.0, 49/255.0), # same as CSS color
	("R", "-"): (255/255.0, 227/255.0, 223/255.0), # reduced saturation and then matched lightness with D at 95
}

def vote_thumbnail_image_map(vote):
	# We only have an SVG for House votes for certain Congresses.
	if vote.chamber != CongressChamber.house:
		raise Http404()
	if vote.congress not in (112, 113, 114, 115):
		raise Http404()

	# Load the SVG.
	import xml.etree.ElementTree as ET
	tree = ET.parse('static/cd-2014.svg')

	# Fetch color codes per district.
	colors = { }
	for voter in vote.get_voters():
		district = voter.person_role.state.lower() + ("%02d" % voter.person_role.district)
		clr = vote_diagram_colors.get((voter.person_role.party[0], voter.option.key))
		if clr:
			clr = tuple([c*256 for c in clr])
			colors[district] = "rgb(%d,%d,%d)" % clr
	if len(colors) == 0:
		# Does not have any +/- votes.
		raise Http404()

	# Apply.
	for node in tree.getroot():
		color = colors.get(node.get("id"))
		if color:
			node.set("style", "fill:" + color)
		elif node.tag.endswith("polygon"):
			# No voter for this district.
			node.set("style", "fill:white")
		elif node.get("id") == "non-voting-delegates":
			# The non-voting-delegates group holds the districts
			# we should hide because they don't have a vote.
			tree.getroot().remove(node)

	# Send response.
	v = ET.tostring(tree.getroot())
	r = HttpResponse(v, content_type='image/svg+xml')
	r["Content-Length"] = len(v)
	return r

def vote_thumbnail_image_seating_diagram(vote, is_thumbnail):
	
	import cairo, re, math
	from io import StringIO
	
	# general image properties
	font_face = "DejaVu Serif Condensed"
	image_width = 300
	image_height = 250 if is_thumbnail else 170
	
	# format text to print on the image
	vote_title = re.sub(r"^On the Motion to ", "To ", vote.question)
	if re.match(r"Cloture .*Rejected", vote.result):
		vote_result_2 = "Filibustered"
	elif re.match(r"Cloture .*Agreed to", vote.result):
		vote_result_2 = "Proceed"
	elif re.match(r"Veto Overridden", vote.result):
		vote_result_2 = "Overridden"
	elif re.match(r"Veto Sustained", vote.result):
		vote_result_2 = "Sustained"
	elif re.match(r".* Not Sustained$", vote.result):
		vote_result_2 = "Not Sustained"
	else:
		vote_result_2 = re.sub("^(Bill|Amendment|Resolution of Ratification|(Joint |Concurrent )?Resolution|Conference Report|Nomination|Motion to \S+|Motion) ", "", vote.result)
	if vote_result_2 == "unknown": vote_result_2 = ""
	if len(vote_result_2) > 15: vote_result_2 = vote_result_2[-15:]
	if vote_result_2 == "Confirmed": vote_title = re.sub(r"^On the Nomination ", "", vote_title)
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
		for i in range(len(totals["parties"])):
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
	if is_thumbnail:
		# Title
		ctx.set_font_size(16)
		ctx.set_source_rgb(.2,.2,.2)
		ctx.move_to(150,10)
		show_text_centered(ctx, vote_title, max_width=.95*image_width)
		chart_top = 50
	
	# Vote Tally
	font_size = 24 if len(vote_result_2) < 10 else 20
	ctx.set_font_size(font_size)
	ctx.set_source_rgb(.1, .1, .1)
	ctx.move_to(150,chart_top)
	show_text_centered(ctx, vote_result_1)
	
	# Vote Result
	ctx.move_to(150,chart_top+8+font_size)
	show_text_centered(ctx, vote_result_2) 
	w = max(ctx.text_extents(vote_result_1)[2], ctx.text_extents(vote_result_2)[2])
	
	# Line
	ctx.set_line_width(1)
	ctx.new_path()
	ctx.line_to(150-w/2, chart_top+3+font_size)
	ctx.rel_line_to(w, 0)
	ctx.stroke()
	
	if is_thumbnail:
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
	inner_r = w/2 * 1.25 + .4 * font_size # wrap closely around the text in the middle
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
	for row in range(seating_rows):
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
		for i in range(count):
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
			voters = vote.get_voters()
			
			# Store ideology scores
			for voter in voters:
				if voter.option.key not in ("+", "-"): continue
				party = party_index.get(voter.party, 1)
				option = 0 if voter.option.key == "+" else 1
				coord =  ideology_scores[vote.congress].get(voter.person.id if voter.person else "UNKNOWN",
					ideology_scores[vote.congress].get("MEDIAN:" + (voter.party or ""),
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
			for i in range(n_voters):
				seats[seat_idx] = (seats[seat_idx], (party, vote)) 
				seat_idx += 1
	
	else:
		# Assign voters to seats in order.
		for i in range(len(voter_details)):
			seats[i] = (seats[i], voter_details[i][1])

	# Draw the seats.
	
	for ((row, seat_pos), (party, vote)) in seats:	
		# radius of this row (again, code dup)
		if seating_rows > 1:
			r = inner_r + (outer_r-inner_r) * row / float(seating_rows-1)
		else:
			r = inner_r
		
		# draw
		ctx.set_source_rgb(*vote_diagram_colors[(["D", "I", "R"][party], ["+", "-"][vote])])
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

@anonymous_view
@render_to('vote/presidential_candidates.html')
def presidential_candidates(request):
	return { }

@anonymous_view
@render_to('vote/comparison.html')
def vote_comparison_table_named(request, table_id, table_slug):
	# Validate URL.
	if int(table_id) == 1:
		if table_slug != "trump-nominations":
			return HttpResponseRedirect("/congress/votes/compare/1/trump-nominations")
		title = "Key Trump Nominations"
		description = "Senate votes on key Trump nominations."
		votes = [
			("115-2017/s29", { "title": "Mattis—Defense", "longtitle":  "James Mattis to be Secretary of Defense" }),
			("115-2017/s30", { "title": "Kelly—Homeland Security", "longtitle": "John Kelly to be Secretary of Homeland Security" }),
			("115-2017/s32", { "title": "Pompeo—CIA", "longtitle": "Mike Pompeo to be Director of the Central Intelligence Agency" }),
			("115-2017/s33", { "title": "Haley—UN Ambassador", "longtitle": "Nikki Haley to be the Ambassador to the United Nations" }),
			("115-2017/s35", { "title": "Chao—Transportation", "longtitle": "Elaine Chao to be Secretary of Transportation" }),
			("115-2017/s36", { "title": "Tillerson—State", "longtitle": "Rex Tillerson to be Secretary of State" }),
			("115-2017/s54", { "title": "DeVos—Education", "longtitle": "Elisabeth DeVos to be Secretary of Education" }),
			("115-2017/s59", { "title": "Sessions—Attorney General", "longtitle": "Jeff Sessions to be Attorney General" }),
			("115-2017/s61", { "title": "Price—HHS", "longtitle": "Thomas Price to be Secretary of Health and Human Services" }),
			("115-2017/s63", { "title": "Mnuchin—Treasury", "longtitle": "Steven Mnuchin to be Secretary of the Treasury" }),
			("115-2017/s64", { "title": "Shulkin—VA", "longtitle": "David Shulkin to be Secretary of Veterans Affairs" }),
			("115-2017/s65", { "title": "McMahon—SBA", "longtitle": "Linda McMahon to be Administrator of the Small Business Administration" }),
			("115-2017/s68", { "title": "Mulvaney—OMB", "longtitle": "Mick Mulvaney to be Director of the Office of Management and Budget" }),
			("115-2017/s71", { "title": "Pruitt—EPA", "longtitle": "Scott Pruitt to be Administrator of the Environmental Protection Agency" }),
		]
	elif int(table_id) == 2:
		if table_slug != "trump-impeachment":
			return HttpResponseRedirect("/congress/votes/compare/2/trump-impeachment")
		title = "Comparing Votes Impeaching President Trump"
		description = "House votes on resolutions of impeachment of the President."
		votes = [
			("115-2017/h658", { "title": "On Motion to Table Resolution of Impeachment H.Res. 646" }),
			("115-2018/h35", { "title": "On Motion to Table Resolution of Impeachment H.Res. 705" }),
		]
	elif int(table_id) == 4:
		if table_slug != "balanced-budget-amendment-2018":
			return HttpResponseRedirect("/congress/votes/compare/4/balanced-budget-amendment-2018")
		title = "Comparing Votes on Tax Cuts, the Omnibus Spending Bill, and the Balanced Budget Amendment"
		description = "The House recently voted to cut taxes (Tax Cuts and Jobs Act, Dec. 20, 2017), increase spending (Consolidated Appropriations Act, Mar. 22, 2018), and --- quixotically --- require that the federal budget be balanced without a three-fifths vote in both chambers (Balanced Budget Amendment, Apr. 12, 2018)."
		votes = [
			("115-2017/h699", { "title": "Tax Cuts and Jobs Act" }),
			("115-2018/h127", { "title": "Consolidated Appropriations Act" }),
			("115-2018/h138", { "title": "Balanced Budget Amendment" }),
		]
	else:
		raise Http404()

	# Compute matrix.
	votes, party_totals, voters = get_vote_matrix(votes)

	# Return.
	return {
		"title": title,
		"description": description,
		"votes": votes,
		"party_totals": party_totals,
		"voters": voters,
		"col_width_pct": int(round(100/(len(votes)+1))),
	}

@anonymous_view
@render_to('vote/comparison.html')
def vote_comparison_table_arbitrary(request, vote_ids):
    # Get votes to show.
    votes = []
    for vote_id in vote_ids.split(","):
        try:
            vote = get_object_or_404(Vote, id=vote_id)
        except ValueError:
            raise Http404()
        votes.append(vote)

    # Compute matrix.
    votes, party_totals, voters = get_vote_matrix(votes)

    # Return.
    return {
        "title": "Vote Comparison",
        "description": "",
        "votes": votes,
        "party_totals": party_totals,
        "voters": voters,
        "col_width_pct": int(round(100/(len(votes)+1))),
    }

def get_vote_matrix(votes, filter_people=None, tqdm=lambda _ : _):
	# Convert votes array to Vote instances with extra fields attached as instance fields.
	# votes is an array of tuples of the form
	# (Vote instance | Vote id, Vote slug, { extra dict info })
	# or an array of just the first part of the tuple.

	def fetch_vote(item):
		if isinstance(item, tuple):
			id, extra = item
		else:
			id = item
			extra = { }

		# Fetch vote.
		if isinstance(id, int):
			vote = Vote.objects.get(id=id)
		elif isinstance(id, Vote):
			vote = id
		else:
			import re
			m = re.match(r"^(\d+)-(\w+)/([hs])(\d+)$", id)
			if not m:
				raise Http404(id)
			congress, session, chamber, number = m.groups()
			try:
				vote = load_vote(congress, session, chamber, number)
			except Http404:
				raise ValueError("Vote ID is not valid: " + id)

		# Add additional user-supplied fields.
		for k, v in extra.items():
			setattr(vote, k, v)

		# Return
		return vote

	votes = [fetch_vote(item) for item in votes]

	# Compute totals by party, which yields a matrix like the matrix for voters
	# where the rows are parties and in each row the 'votes' key provides columns
	# for the votes.

	if not filter_people:
		party_totals = { }
		for i, vote in enumerate(votes):
			totals = vote.totals()
			for party, party_total in zip(totals['parties'], totals['party_counts']):
				pt = party_totals.setdefault(party, {
					"party": party,
					"total_votes": 0,
					"votes": [None] * len(votes), # if this party didn't occur in prev votes, make sure we have an empty record
				})
				pt["total_votes"] += party_total["total"]
				pt["votes"][i] = party_total
		party_totals = sorted(party_totals.values(), key = lambda value : -value['total_votes'])
		party_sort_order = [party_total["party"] for party_total in party_totals]

	# Is more than one chamber involved here?
	more_than_one_chamber = (len(set(v.chamber for v in votes)) > 1)

	# Compute the rows of the matrix.

	voters = { }
	for i, vote in enumerate(tqdm(votes)):
		for voter in vote.get_voters(filter_people=filter_people):
			if filter_people and voter.person not in filter_people: continue
			v = voters.setdefault(voter.person_id, {
				"person": voter.person,
				"total_plus": 0,
				"total_votes": 0,
				"votes": [None for _ in votes],
			})

			v["votes"][i] = voter
			if voter.option.key == "+":
				v["total_plus"] += 1
			if voter.option.key not in ("0", "P"):
				v["total_votes"] += 1

			# Add name info at the moment of the vote.
			from person.name import get_person_name
			voter.person.role = voter.person_role
			voter.person.role.party = voter.party # party at this moment
			v["votes"][i].person_name = get_person_name(voter.person, firstname_position='after', show_district=True, show_title=False, show_type=more_than_one_chamber, show_party=False)

	# Choose one name & party & state-district (for sort).
	for voter in voters.values():
		names = set(v.person_name for v in voter["votes"] if v is not None)
		if len(names) == 1:
			voter["person_name"] = list(names)[0]
		else:
			voter["person_name"] = get_person_name(voter["person"], firstname_position='after', show_district=False, show_title=False, show_type=more_than_one_chamber, show_party=False)

		parties = set(v.party for v in voter["votes"] if v is not None)
		if len(parties) == 1:
			voter["party"] = list(parties)[0]
			voter["party_order"] = party_sort_order.index(voter["party"])

		roles = set((v.person_role.state, str(v.person_role.role_type), str(v.person_role.senator_rank), ("%02d" % v.person_role.district if v.person_role.district else "")) for v in voter["votes"] if v is not None)
		if len(roles) == 1:
			voter["state_district"] = "-".join(list(roles)[0])

	# Default sort order.
	voters = sorted(voters.values(), key = lambda value : value['person_name'])

	return votes, party_totals if not filter_people else None, voters

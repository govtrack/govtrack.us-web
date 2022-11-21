# -*- coding: utf-8 -*-
import csv
from io import StringIO, BytesIO
from datetime import datetime

from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
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
        #paginate = lambda form : "session" not in form, # people like to see all votes for a year on one page
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
    voters.sort(key = lambda x : (x.option.key, x.person_role.party if x.person and x.person_role and x.person_role.party else "", x.person.name_no_details_lastfirst() if x.person else x.get_voter_type_display()))

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
            for ideolog in csv.reader(open("data/analysis/by-congress/%d/sponsorshipanalysis_%s.txt" % (congress, ch))):
                if ideolog[0] == "ID": continue # header row
                if float(ideolog[2]) <  .1: continue # very low leadership score, ideology is not reliable
                ideology_scores[congress][int(ideolog[0])] = float(ideolog[1])
                scores_by_party.setdefault(ideolog[4].strip(), []).append(float(ideolog[1]))
            ideology_scores[congress]["MEDIAN"] = median(list(ideology_scores[congress].values()))
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
            voter.person.name_no_district() if voter.person else voter.get_voter_type_display(),
            voter.party])
    output = outfile.getvalue()
    firstline = '%s Vote #%d %s - %s\n' % (vote.get_chamber_display(), vote.number,
                                         vote.created.isoformat(), vote.question) # strftime doesn't work on dates before 1900
    output = firstline + output
    if 'inline' not in request.GET:
        r = HttpResponse(output, content_type='text/csv; charset=utf-8')
        r['Content-Disposition'] = 'attachment; filename=' + vote.get_absolute_url()[1:].replace("/", "_") + ".csv"
    else:
        r = HttpResponse(output, content_type='text/plain; charset=utf-8')
    return r


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
		body, mime_type = vote_thumbnail_image_map(vote)
	elif image_type == "diagram":
		# Seating diagram.
		body, mime_type = vote_thumbnail_image_seating_diagram(vote, include_result=False)
	elif image_type == "thumbnail":
		# Small square thumbnail.
		body, mime_type = vote_thumbnail_small(vote)
	elif image_type == "card":
		# Twitter card wide thumbnail.
		body, mime_type = vote_thumbnail_wide(vote)
	else:
		raise Http404()

	# Return response.
	r = HttpResponse(body, content_type=mime_type)
	r["Content-Length"] = len(body)
	return r

vote_diagram_colors = { # see also person.views.membersoverview
	("D", "+"): (0/255.0, 142/255.0, 209/255.0), # same as CSS color
	("D", "-"): (213/255.0, 244/255.0, 255/255.0), # reduced saturation and then matched lightness with R at 95
	("I", "+"): (0.07, 0.05, 0.07),
	("I", "-"): (0.85, 0.85, 0.85),
	("R", "+"): (248/255.0, 54/255.0, 49/255.0), # same as CSS color
	("R", "-"): (255/255.0, 227/255.0, 223/255.0), # reduced saturation and then matched lightness with D at 95
}

def vote_thumbnail_small(vote):
	# Try producing the map diagram, and if that's not available, then
	# the seating diagram.
	try:
		body, mime_type = vote_thumbnail_image_map(vote)
		# This is SVG so return it directly.
		return body, mime_type
	except Http404:
		body, mime_type = vote_thumbnail_image_seating_diagram(vote)

	# Scale down the image.
	from PIL import Image
	im = Image.open(BytesIO(body))
	im.thumbnail((100,100))

	# Rasterize it again.
	buf = BytesIO()
	im.save(buf, "PNG")

	# Return the image.
	return (buf.getvalue(), "image/png")

def vote_thumbnail_image_map(vote):
	# We only have an SVG for House votes for certain Congresses.
	if vote.chamber != CongressChamber.house:
		raise Http404()

	if vote.congress in (112, 113, 114, 115, 116, 117):
		# Although there were some minor changes in district boundaries over
		# this time period, there weren't changes in the total number of
		# districts in each state, so we're glossing over the geographic changes.
		cartogram_year = 2014
	else:
		raise Http404()

	# Load the SVG.
	import xml.etree.ElementTree as ET
	tree = ET.parse(f'static/cd-{cartogram_year}.svg')

	# Fetch color codes per district and make SVG CSS styles.
	styles = { }
	for voter in vote.get_voters():
		if not voter.person_role: continue # some votes cannot map voters to roles such as when there are mismatches w/ the term start/end dates
		if voter.option.key not in ("+", "-"): continue # don't know what color to assign here
		district = voter.person_role.state.lower() + ("%02d" % voter.person_role.district)
		clr = vote_diagram_colors.get((voter.person_role.party[0], "+"))
		if clr:
			clr = tuple([c*256 for c in clr])
			if voter.option.key == "+":
				styles[district] = "fill: rgb(%d,%d,%d); stroke: #AAA; strike-width: 1px;" % clr
			else:
				styles[district] = "fill: transparent; stroke: rgb(%d,%d,%d); strike-width: 1px;" % clr
	if len(styles) == 0:
		# Does not have any +/- votes.
		raise Http404()

	# Apply.
	for node in tree.getroot():
		style = styles.get(node.get("id"))
		if style:
			node.set("style", style)
		elif node.tag.endswith("polygon"):
			# No voter for this district.
			node.set("style", "fill: white; stroke: #666; stroke-width: 1px;")
		#elif node.get("id") == "non-voting-delegates":
		#	# The non-voting-delegates group holds the districts
		#	# we should hide because they don't have a vote.
		#	tree.getroot().remove(node)

	# Send raw SVG response.
	return (ET.tostring(tree.getroot()), "image/svg+xml")

def vote_thumbnail_wide(vote):
    import cairo, re

    image_width, image_height = (600, 300) # 2:1
    im, ctx = create_image(image_width, image_height)

    # Title
    vote_title = re.sub(r"^(On the )?Motion to Invoke ", "", vote.question)
    vote_title = re.sub(r"^(On the )?Motion to ", "To ", vote.question)
    vote_title = re.sub(r"^(On the )?Motion ", "Motion ", vote_title)
    vote_title = re.sub(r"^On the Nomination ", "", vote_title)
    ctx.select_font_face(FONT_FACE, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(16)
    ctx.set_source_rgb(.2,.2,.2)
    ctx.move_to(image_width/2, 10)
    show_text_centered(ctx, vote_title, max_width=.95*image_width)

    # Vote Chamber/Date/Number
    vote_date = vote.created.strftime("%x") if vote.created.year > 1900 else vote.created.isoformat().split("T")[0]
    vote_citation = vote.get_chamber_display() + " Vote #" + str(vote.number) + " -- " + vote_date
    ctx.select_font_face(FONT_FACE, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(14)
    ctx.move_to(image_width/4, image_height-25)
    show_text_centered(ctx, vote_citation, max_width=image_width/2*.95) 

    # Convert the image buffer to raw PNG bytes.
    buf = BytesIO()
    im.write_to_png(buf)

    # Load it into PIL and add the sub-images.
    from PIL import Image
    im = Image.open(buf)

    # Make the seating diagram.
    seating_diagram_width = 280
    seating_diagram = Image.open(BytesIO(vote_thumbnail_image_seating_diagram(vote, 280, 175)[0]))
    im.paste(seating_diagram, (image_width//4-seating_diagram_width//2,75))

    # Show some legislators - outliers first. Select randomly.
    legislator_count = 6
    import random
    voters = vote.get_voters()
    get_vote_outliers(voters)
    random.shuffle(voters) # first shuffle
    voters.sort(key = lambda v : not v.is_outlier) # put outliers first, but otherwise keeping the shuffled order
    selected_voters = []
    while len(selected_voters) < legislator_count and len(voters) > 0:
        v = voters.pop(0)
        if not v.person_role: continue
        if not v.person.has_photo(): continue
        selected_voters.append(v)

    # Paste a block for each legislator.
    for i, v in enumerate(selected_voters):
        # Paste photo.
        photo_width = int(image_width/8)
        photo_height = int(photo_width*1.2)
        caption_height = 33
        x = int( image_width//2 + 20 + (i % 3) * photo_width*1.2 )
        y = int( 40 + (i // 3) * (photo_height+caption_height*1.25) )
        try:
            rect_color = vote_diagram_colors[(v.party[0], v.option.key)]
            rect_color = tuple(int(255*x) for x in rect_color) # float to int
        except:
            # If the party or option key doesn't have a color, skip.
            rect_color = (0,0,0)
        bg_clr = (1,1,1)
        fg_clr = (0,0,0)
        try:
            bg_clr = vote_diagram_colors[(v.party[0], v.option.key)]
            if v.option.key == "+":
                fg_clr = (1,1,1)
        except:
            # If the party or option key doesn't have a color, skip.
            pass

        draw_legislator_image(im, x, y, photo_width, photo_height, v.person, rect_color, caption_height, bg_clr, fg_clr, "· " + v.option.value + " ·")

    # Rasterize it again.
    buf = BytesIO()
    im.save(buf, "PNG")

    # Return the image.
    return (buf.getvalue(), "image/png")

def draw_legislator_image(im, x, y, width, height, person, rect_color, caption_height, caption_bg_color, caption_fg_color, caption_extra_text):
    # Open the legislator's photo.
    import cairo
    from PIL import Image, ImageDraw
    photo = Image.open(open("." + person.get_photo_url(100 if width <= 100 else 200), "rb"))
    photo.thumbnail((width, height))

    # Paste it into the target image buffer.
    im.paste(photo, (x, y))

    # Draw a rectange around the photo.
    draw = ImageDraw.Draw(im)
    draw.rectangle(((x, y), (x+photo.size[0]-1, y+photo.size[1])), outline=rect_color, fill=None)

    # Make a temporary buffer for the text.
    im2 = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, caption_height)
    ctx2 = cairo.Context(im2)

    # clear background
    ctx2.set_source_rgba(*caption_bg_color)
    ctx2.new_path()
    ctx2.line_to(0, 0)
    ctx2.line_to(width, 0)
    ctx2.line_to(width, caption_height)
    ctx2.line_to(0, caption_height)
    ctx2.fill()

    # write text
    font_size = caption_height * .6
    if caption_extra_text: font_size /= 1.85
    ctx2.set_source_rgb(*caption_fg_color)
    ctx2.select_font_face(FONT_FACE, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx2.set_font_size(font_size)
    ctx2.move_to(width/2, 2+font_size*1.05)
    show_text_centered(ctx2, person.lastname, max_width=width-4, use_baseline=True)
    ctx2.select_font_face(FONT_FACE, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx2.set_font_size(font_size*.9)
    ctx2.move_to(width/2, 2+font_size*2.25)
    show_text_centered(ctx2, caption_extra_text, use_baseline=True)

    # copy into main raster
    buf = BytesIO()
    im2.write_to_png(buf)
    im2 = Image.open(buf)
    im.paste(im2, (x, y+height))

FONT_FACE = "DejaVu Serif Condensed"

def create_image(image_width, image_height, bg_color=(1,1,1,1)):
    import cairo

    im = cairo.ImageSurface(cairo.FORMAT_ARGB32, image_width, image_height)
    ctx = cairo.Context(im)

    # clear background
    ctx.set_source_rgba(*bg_color)
    ctx.new_path()
    ctx.line_to(0, 0)
    ctx.line_to(image_width, 0)
    ctx.line_to(image_width, image_height)
    ctx.line_to(0, image_height)
    ctx.fill()

    return (im, ctx)

def show_text_centered(ctx, text, max_width=None, use_baseline=False):
    import re
    while True:
        (x_bearing, y_bearing, width, height, x_advance, y_advance) = ctx.text_extents(text)
        if use_baseline:
            height = 0
        if max_width is not None and width > max_width:
            # Chop off a word if possible and replace with ellisis.
            text2 = re.sub(r" \S+[ \.…]*?$", "…", text)
            if text2 == text:
                # If there was no word to chop off, just chop off
                # any letter.
                text2 = re.sub(r".[ \.…]*?$", "…", text)
            text = text2
            continue
        break
        
    ctx.rel_move_to(-width/2, height)
    ctx.show_text(text)

def vote_thumbnail_image_seating_diagram(vote, image_width=330, image_height=190, include_result=True):
	import cairo, re, math
	
	# format text to print on the image
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
		vote_result_2 = re.sub("^(Bill|Amendment|Resolution of Ratification|(Joint |Concurrent )?Resolution|Conference Report|Nomination|Motion to \S+|Motion|Motion for Attendance) ", "", vote.result)
	if vote_result_2 == "unknown": vote_result_2 = ""
	if len(vote_result_2) > 15: vote_result_2 = vote_result_2[-15:]
	
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
	
	if not include_result:
		image_height -= 20
	im, ctx = create_image(image_width, image_height)
	
	ctx.select_font_face(FONT_FACE, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
	
	# Vote Tally
	font_size = (24 if len(vote_result_2) < 10 else 20) * image_width / 300
	ctx.set_font_size(font_size)
	ctx.set_source_rgb(.1, .1, .1)
	ctx.move_to(image_width/2, 0 if include_result else 8)
	show_text_centered(ctx, vote_result_1)
	w = ctx.text_extents(vote_result_1)[2]
	seating_center_y = 10
	
	# Vote Result
	if include_result:
		# Text
		ctx.move_to(image_width/2, 8+font_size)
		show_text_centered(ctx, vote_result_2)
		w = max(w, ctx.text_extents(vote_result_2)[2])
	
		# Line
		ctx.set_line_width(1)
		ctx.new_path()
		ctx.line_to(image_width/2-w/2, 3+font_size)
		ctx.rel_line_to(w, 0)
		ctx.stroke()

		# Shift diagram down.
		seating_center_y = 25
	
	# Seats
	
	# Construct an array of rows of seats, where each entry maps to a particular
	# voter.
	
	# How many rows of seats? That is hard coded by chamber.
	seating_rows = 8 if vote.chamber == CongressChamber.house else 4
		# 4 for Senate (http://www.senate.gov/artandhistory/art/special/Desks/chambermap.cfm)
		# about 8 for the House
		
	# Long ago Congress had very few people.
	seating_rows = min(total_count, total_count // 8 + 1, seating_rows)
		
	# Determine the seating chart dimensions: the radius of the inside row of
	# seats and the radius of the outside row of seats.
	inner_r = w/2 * 1.25 + .4 * font_size # wrap closely around the text in the middle
	inner_r = max(inner_r, 75 if seating_rows <= 4 else 50) # don't make the inner radius too small
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
		ctx.set_source_rgba(*( list(vote_diagram_colors[(["D", "I", "R"][party], "+")]) + [1 if vote == 0 else .3] ))
		ctx.identity_matrix()
		ctx.translate(image_width/2, seating_center_y)
		p = seat_pos/float(rowcounts[row]-1)
		ctx.rotate(3.14159 * (1 - p))
		ctx.translate(r, 0)
		def sigmoid(x): return 1 / (1 + math.exp(- (x*2-1)*2 )) # row is steepnesss
		ctx.rotate(3.14159 * (sigmoid(p) - p))
		if vote > 0:
			ctx.scale(.9, .9) # stroke rects look bigger than filled rects otherwise
		ctx.rectangle(-seat_size/2, -seat_size/2, seat_size, seat_size)
		if vote == 0:
			ctx.fill()
		else:
			ctx.stroke()

	# Convert the image buffer to raw PNG bytes and return it.
	buf = BytesIO()
	im.write_to_png(buf)
	return (buf.getvalue(), "image/png")

@anonymous_view
def vote_check_thumbnails(request):
    votes = Vote.objects.filter(congress=CURRENT_CONGRESS)\
        .order_by("congress", "session", "chamber", "number")
    ret = ""
    for v in votes:
        ret += """<div><a href="%s"><img src="%s" style="border: 1px solid #777"/></a></div>\n""" % (v.get_absolute_url(), v.get_absolute_url() + "/card")
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
	elif int(table_id) == 5:
		if table_slug != "senate-nuclear-option":
			return HttpResponseRedirect("/congress/votes/compare/5/senate-nuclear-option")
		title = "The Nuclear Option"
		description = "The so-called Nuclear Option in the Senate is a simple majority vote to change the rules regarding \"cloture\" votes with a 3/5ths threshold. In each vote below, a \"no\" vote was a vote to change the rules and eliminate some aspect of the filibuster. A \"yes\" vote was a vote to preserve the long-standing filibuster rules."
		votes = [
			("113-2013/s242", { "title": "Keeping Filibuster for Most Nominees" }),
			("115-2017/s109", { "title": "Keeping Filibuster for Supreme Court Nominees" }),
			("116-2019/s59",  { "title": "Keeping Filibuster 30-Hour Length for Most Nominees" }),
		]
	elif int(table_id) == 6:
		if table_slug != "ndaa-2021":
			return HttpResponseRedirect("/congress/votes/compare/6/ndaa-2021")
		title = "Legislators Who Changed Their Vote on the 2021 NDAA"
		description = "After President Trump vetoed the National Defense Authorization Act, the defense spending bill, for 2021, some legislators changed their position."
		votes = [
			("116-2020/h238", { "title": "House Vote on Passage" }),
			("116-2020/h253",  { "title": "House Veto Override" }),
			#("116-2020/s264", { "title": "Senate Vote on Passage" }),
		]
	elif int(table_id) == 7:
		if table_slug != "2021-coup-attempt":
			return HttpResponseRedirect("/congress/votes/compare/7/2021-coup-attempt")
		title = "Legislators Who Voted to Exclude States from the Electoral College Count on January 6, 2021"
		description = "Following a terrorist attack on the Capitol to prevent the counting of the Electoral College votes and the selection of the next President, these legislators voted to exclude Arizona and Pennsylvania from the count based on the same lies, conspiracy theories, and preposterous legal arguments that inspired the attack"
		votes = [
			("117-2021/s1", { "title": "Senate Vote to Exclude Arizona" }),
			("117-2021/h10", { "title": "House Vote to Exclude Arizona" }),
			("117-2021/s2", { "title": "Senate Vote to Exclude Pennsylvania" }),
			("117-2021/h11", { "title": "House Vote to Exclude Pennsylvania" }),
		]
	else:
		raise Http404()

	# Compute matrix.
	votes, party_totals, voters = get_vote_matrix(votes)

	# Return.
	return {
		"html_title": title,
		"h1_title": title,
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
    # Allow integer vote IDs (primary keys in our database) or
    # congress project-style IDs.
    votes = []
    for vote_id in vote_ids.split(","):
        try:
            vote_id_int = int(vote_id)
            try:
                vote = get_object_or_404(Vote, id=vote_id)
            except ValueError:
                raise Http404()
        except ValueError:
            try:
                vote = Vote.from_congressproject_id(vote_id)
            except Vote.DoesNotExist:
                raise Http404()
        votes.append(vote)

    # Votes list as a string.
    votes_list = ",".join([vote.congressproject_id for vote in votes])

    # Compute matrix.
    votes, party_totals, voters = get_vote_matrix(votes)

    # Download as CSV?
    if request.GET.get("download", "") == "csv":
        outfile = StringIO()
        writer = csv.writer(outfile)
        writer.writerow(["", ""] + [vote.question for vote in votes])
        writer.writerow(["", ""] + ["https://www.govtrack.us" + vote.get_absolute_url() for vote in votes])
        for voter in voters:
            writer.writerow([voter["person_name"], voter["party"]] + [opt.option.value if opt else "" for opt in voter["votes"]])
        output = outfile.getvalue()
        r = HttpResponse(output, content_type='text/csv; charset=utf-8')
        r['Content-Disposition'] = 'attachment; filename=vote_comparison_{}.csv'.format("-".join(str(vote.id) for vote in votes))
        #r = HttpResponse(output, content_type='text/plain; charset=utf-8')
        return r

    # Return.
    return {
        "html_title": "Vote Comparison ({})".format(", ".join(votes_list.split(","))),
        "h1_title": "Custom Vote Comparison",
        "description": "",
        "votes": votes,
        "votes_list": votes_list,
        "party_totals": party_totals,
        "voters": voters,
        "col_width_pct": int(round(100/(len(votes)+1))),
    }

def vote_comparison_table_arbitrary_add(request):
    # Combine the vote_cmp_list cookie set on the last page view of the comparison
    # page with the vote query string parameter, and redirect to the comparison page
    # with those votes.
    import urllib.parse # the comma comes back as %2C
    vote_comparison_list = []
    for s in urllib.parse.unquote(request.COOKIES.get('vote_cmp_list', '')).split(","):
        try:
            vote_comparison_list.append(Vote.from_congressproject_id(s))
        except:
            pass
    try:
        vote_comparison_list.append(Vote.from_congressproject_id(request.GET.get("vote", "")))
    except:
        pass
    if len(vote_comparison_list) == 0:
        raise Http404()
    return HttpResponseRedirect("/congress/votes/compare/" + ",".join(v.congressproject_id for v in vote_comparison_list))

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

	# For each vote, make a list of all of the votes except that one for "Remove" links.
	for vote in votes:
		vote.comparison_remove_me_list = ",".join([vote2.congressproject_id for vote2 in votes if vote2 != vote])

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

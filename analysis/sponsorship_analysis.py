#!script

# Compute a Markov transition matrix representing the cosponsorship patterns
# of representatives and (separately) senators for a given time period.
# Each transition is from a Member of Congress to another Member of Congress
# if the former cosponsors a bill of the latter. The matrix is constructed so that
# the columns represent the transition probabilities (i.e. columns sum to 1).
#
# From the transition matrix we compute "PageRanks", which are essentially
# implicit leadership scores based on Member cosponsorship behavior, and
# an ideological score based on a singular value decomposition of the matrix
# rank reduction, using the 2nd dimension.
#
# Finally, plot these two dimensions.
#
# To update historical data:
# for c in {93..113}; do echo $c; analysis/sponsorship_analysis.py $c; done

import sys
import os
import glob
import math
import numpy
import scipy.stats
import lxml.etree as lxml

from person.models import PersonRole
from person.types import RoleType
from bill.models import Bill, Cosponsor
from us import get_congress_dates

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# CONFIGURATION

datadir = "data"
matplotlib.rcParams["font.size"] = 9.0
matplotlib.rcParams["lines.markersize"] = 3

# GLOBAL FUNCTIONS

def onenorm(u):
	# The one-norm.
	return sum(abs(u))

def rescale(u, log=False):
	# Re-scale the vector to range from 0 to 1, and convert it out of
	# numpy data format.
	u = (u - min(u)) / (max(u) - min(u))
	
	# If log is True, then rescale the values on an essentially logarithmic
	# axis, such that the median value comes out as linearly halfway
	# between the min and maximum values. Note that the unscaled
	# min and max are 0 and 1, respectively, since we already rescaled
	# above. Thus:
	#    1/2*(log(0 + s) + log(1 + s)) = log(median + s)
	# Wolfram|Alpha says the solution is:
	#    s = -m^2/(2m-1)
	if log:
		m = numpy.median(u)
		s = -m**2/(2*m - 1)
		u = numpy.log(u + s)
		u = (u - min(u)) / (max(u) - min(u))
	return [float(v) for v in u]

# BEGIN

def get_roles_of_people(congressnumber):
	congress_dates = get_congress_dates(congressnumber)
	return PersonRole.objects.filter(
		role_type__in=(RoleType.senator, RoleType.representative),
		startdate__lt=congress_dates[1], # start dates of next congress are on this day too
		enddate__gt=congress_dates[0] # end dates from previous congress are on this day too
		).select_related("person")\
		.order_by('-startdate')  # so we put people in the right list by their most recent term

def get_people(roles):
	# Put each person only in the House or Senate output, even if they served in both,
	# according to their most recent role. We want to include everyone who served
	# during the Congress, even if they are not now serving.
	people = { }
	people_list = { 'h': set(), 's': set() }

	for person_role in roles:
		pid = person_role.person_id
		if pid in people: continue # saw a more recent term for this person
		people[pid] = person_role
		people_list["h" if person_role.role_type == RoleType.representative else "s"].add(pid)

	return people, people_list

def attach_other_stats(congressnumber, person_role):
	# A staffer tells me they're interested in the number of unique/total cosponsors to their
	# bills in the current Congress. We'll compute that here too. For historical data, compute for
	# bills up to the end of the Congress.
	bills = person_role.person.sponsored_bills.filter(congress=congressnumber)
	cosp = Cosponsor.objects.filter(bill__in=list(bills)).values_list('person', flat=True)
	person_role.total_cosponsors = len(cosp)
	person_role.unique_cosponsors = len(set(cosp))

	# ...and the number of other people's bills the member has cosponsored this Congress.
	person_role.total_cosponsored_bills = Cosponsor.objects.filter(person=person_role.person, bill__congress=congressnumber).count()

	# ...and the number of bills the Member introduced this Congress
	person_role.total_introduced_bills = Bill.objects.filter(sponsor=person_role.person, congress=congressnumber).count()


def build_matrix(congressnumber, starting_congress, house_or_senate, people, people_list, filter_startdate=None, filter_enddate=None):
	start_date = None
	end_date = None
	
	# Map GovTrack person IDs to rows (or columns) of the matrix.
	rep_to_row = { }
	def rownum(id):
		if not id in rep_to_row:
			rep_to_row[id] = len(rep_to_row)
		return rep_to_row[id]
		
	# Store a flat (i.e. sparse) list of all cells that have the value 1. Note that
	# we will get duplicates here! Scan the indicated and the previous congress,
	# but include only those Members of Congress that served in the indicated
	# Congress.
	cells = []
	for cn in xrange(starting_congress, congressnumber+1):
		for billfilename in glob.glob(datadir + "/us/" + str(cn) + "/bills/" + house_or_senate + "*.xml"):
			xml = lxml.parse(billfilename)
			
			# get the sponsor
			spx = xml.xpath("sponsor/@id")
			if len(spx) == 0: # e.g. debt limit with no sponsor
				continue
			if not int(spx[0]) in people_list[house_or_senate]:
				continue
			sponsor = rownum(int(spx[0]))

			# loop through the cosponsors
			has_entry = False
			for cosponsor_node in xml.xpath("cosponsors/cosponsor"):
				# get the cosponsor's ID
				cosponsor_id = int(cosponsor_node.xpath("string(@id)"))
				if cosponsor_id not in people_list[house_or_senate]: continue

				# if a date filter is specified, only take cosponsors that joined within
				# the date range (inclusive)
				if filter_startdate:
					join_date = cosponsor_node.xpath("string(@joined)")
					if join_date < filter_startdate or join_date > filter_enddate:
						continue

				# add an entry to the flat list of sponsor-cosponsor pairs
				cosponsor = rownum(cosponsor_id)
				cells.append( (sponsor, cosponsor) )
				has_entry = True

			# if there was a sponsor/cosponsor pair from this bill, extend the
			# start_date/end_date range to cover the introduced date of this bill.
			if has_entry:
				date = xml.xpath("introduced/@datetime")[0]
				start_date = min(start_date, date) if start_date else date
				end_date = max(end_date, date)
	
	# In the event a member of congress neither sponsored nor cosponsored
	# a bill, just give them an empty slot.
	for person in people_list[house_or_senate]:
		rownum(person)

	# Get total number of members of congress seen.
	nreps = len(rep_to_row)
	
	# Turn this into a dense numpy array with cells flagged as 1 if there is such
	# a transition. Keep adding 1s... Start with the identity matrix because
	# every rep should be counted as sponsoring his own bills.
	P = numpy.identity(nreps, numpy.float) # numpy.zeros( (nreps,nreps) )
	for sponsor, cosponsor in cells:
		P[sponsor, cosponsor] += 1.0

	return start_date, end_date, rep_to_row, nreps, P

def smooth_matrix(nreps, P):
	# Take the square root of each cell to flatten out outliers where one person
	# cosponsors a lot of other people's bills.
	for i in xrange(nreps):
		for j in xrange(nreps):
			P[i,j] = math.sqrt(P[i,j])

def build_party_list(rep_to_row, people, nreps):
	parties = [None for i in xrange(nreps)]
	for k, v in rep_to_row.items():
		parties[v] = people[k].party
	return parties

def ideology_analysis(nreps, parties, P):
	# Ideology (formerly "Political Spectrum") Analysis
	###################################################

	# Run a singular value decomposition to get a rank-reduction, one dimension
	# of which should separate representatives on a liberal-conservative scale.
	# In practice it looks like the second dimension works best. Also, this works
	# best before we normalize columns to sum to one. That is, we want cells
	# to be 1 when the column person cosponsors a bill of the row person.
	u, s, vh = numpy.linalg.svd(P)
	spectrum = vh[1,:]
	
	# To make the spectrum left-right, we'll multiply the scores by the sign of
	# the mean score of the Republicans to put them on the right.
	# Actually, since scale doesn't matter, just multiply it by the mean.
	R_scores = [spectrum[i] for i in xrange(nreps) if parties[i] == "Republican"]
	R_score_mean = sum(R_scores)/len(R_scores)
	spectrum = spectrum * R_score_mean

	# Scale the values from 0 to 1.
	spectrum = rescale(spectrum)
	
	return spectrum
	
def leadership_analysis(nreps, P):
	# Leadership Analysis based on the Google PageRank Algorithm
	############################################################

	# For each column, normalize so the sum is one. We started with an
	# identity matrix so even MoCs that only cosponsor their own bills
	# have some data. But if they have so little data, we should fudge
	# it because if they only 'cosponsor' their own bills they will get
	# leadership scores of 0.5.
	for col in xrange(nreps):
		s = sum(P[:,col])
		if s == 0: raise ValueError()
		if s < 10: # min number of cosponsorship data per person
			P[:,col] += (10.0-s)/nreps
			s = 10
		P[:,col] = P[:,col] / s
		
	# Create a random transition vector.
	v = numpy.ones( (nreps, 1) ) / float(nreps)
	
	# This is one minus the weight we give to the random transition probability
	# added into each column.
	c = 0.85
	
	# Create an initial choice for x, another random transition vector.
	x = numpy.ones( (nreps, 1) ) / float(nreps)
	
	# Run the Power Method to compute the principal eigenvector for the matrix,
	# which is, after all, the PageRank.
	
	while True:
		# Compute y = Ax where A is P plus some perturbation with magnitude
		# 1-c that ensures that A is a valid aperiodic, irreducible Markov transition matrix.
		y = c * numpy.dot(P, x)
		w = onenorm(x) - onenorm(y)
		y = y + w*v
		
		# Check the error and terminate if we are within tolerance.
		err = onenorm(y-x)
		if err < .00000000001:
			break
	
		x = y
		
	# Scale the values from 0 to 1 on a logarithmic scale.
	x = rescale(x, log=True)

	return x # this is the pagerank
	
def build_output_columns(rep_to_row, people):
	# Create a list of names in row order.
	ids = [None for k in rep_to_row]
	names = [None for k in rep_to_row]
	other_cols = [None for k in rep_to_row]
	usednames = { }
	for k, v in rep_to_row.items():
		ids[v] = k
		names[v] = people[k].person.lastname
		
		# Check that the name is not a dup of someone else, and if so,
		# append a state (and district) to each.
		if names[v] in usednames:
			k2 = usednames[names[v]]
			
			d = str(people[k].district) if people[k].district is not None else ""
			d2 = str(people[k2].district) if people[k2].district is not None else ""
			names[v] = people[k].person.lastname + " [" + people[k].state  + d + "]"
			names[rep_to_row[k2]] = people[k2].person.lastname + " [" + people[k2].state  + d2 + "]"
		else:
			usednames[names[v]] = k

		other_cols[v] = [people[k].total_introduced_bills, people[k].total_cosponsored_bills, people[k].unique_cosponsors, people[k].total_cosponsors]
	return ids, names, other_cols

def draw_figure(congressnumber, house_or_senate, start_date, end_date, nreps, parties, spectrum, pagerank, names):
	for figsize, figsizedescr in ((1.0, ""), (1.5 if house_or_senate == "s" else 3.0, "_large")):
		fig = plt.figure()
		plt.title(("House of Representatives" if house_or_senate == "h" else "Senate") + ", " + start_date + " to " + end_date)
		plt.xlabel("Ideology")
		plt.ylabel("Leadership")
		plt.xticks([])
		plt.yticks([])	
		
		for party, color in (("Republican", "r"), ("Democrat", "b"), ("Independent", "k")):
			for i in xrange(nreps):
				if parties[i] == party:
					plt.text(spectrum[i], pagerank[i], names[i], color=color, ha="left", weight="light", size=(8 if house_or_senate == "s" else 6)/figsize)
					#print spectrum[i], pagerank[i], names[i].encode("utf8")
			
			ss = [spectrum[i] for i in xrange(nreps) if parties[i] == party]
			pp = [pagerank[i] for i in xrange(nreps) if parties[i] == party]
			plt.plot(ss, pp, "." + color, markersize=3/figsize)
	
		plt.savefig(datadir + "/us/" + str(congressnumber) + "/stats/sponsorshipanalysis_" + house_or_senate + figsizedescr + ".png", dpi=120*figsize, bbox_inches="tight", pad_inches=.02)

def describe_members(nreps, parties, spectrum, pagerank):
	# Describe what kind of person each is....
	descr = [None for x in xrange(nreps)] # allocate some space
	for party in ("Republican", "Democrat", "Independent"):
		ss = [spectrum[i] for i in xrange(nreps) if parties[i] == party]
		pp = [pagerank[i] for i in xrange(nreps) if parties[i] == party]
		
		if party != "Independent": # not enough to actually perform the computation, even if we don't want to use it anyway
			ss_20 = scipy.stats.scoreatpercentile(ss, 20)
			ss_80 = scipy.stats.scoreatpercentile(ss, 80)
			
			pp_20 = scipy.stats.scoreatpercentile(pp, 20)
			pp_80 = scipy.stats.scoreatpercentile(pp, 80)
		
		if party == "Democrat":
			descr_table = [
				["progressive Democratic leader", "moderate Democratic leader", "centrist Democratic leader"],
				["progressive Democrat", "rank-and-file Democrat", "centrist Democrat"],
				["lonely progressive Democratic ", "moderate Democratic follower", "centrist Democratic follower"],
				]
		elif party == "Republican":
			descr_table = [
				["centrist Republican leader", "moderate Republican leader", "conservative Republican leader"],
				["centrist Republican", "rank-and-file Republican", "conservative Republican"],
				["centrist Republican follower ", "moderate Republican follower", "lonley conservative Republican follower"],
				]
				
		else:
			# for independents, score according to the whole chamber
			ss_20 = scipy.stats.scoreatpercentile(spectrum, 20)
			ss_80 = scipy.stats.scoreatpercentile(spectrum, 80)
			
			pp_20 = scipy.stats.scoreatpercentile(pagerank, 20)
			pp_80 = scipy.stats.scoreatpercentile(pagerank, 80)
			
			descr_table = [ # no damn commas
				["left-leaning Independent leader", "moderate Independent leader", "right-leaning Independent leader"],
				["left-leaning Independent", "centrist Independent", "right-leaning Independent"],
				["lonely left-leaning Independent", "lonely centrist Independent", "lonely right-leaning Independent"],
				]
				
		for i in xrange(nreps):
			if parties[i] == party:
				descr[i] = descr_table[2 if pagerank[i] < pp_20 else 1 if pagerank[i] < pp_80 else 0][0 if spectrum[i] < ss_20 else 1 if spectrum[i] < ss_80 else 2]

	return descr
		
def write_stats_to_disk(congressnumber, house_or_senate, nreps, ids, parties, names, spectrum, pagerank, descr, other_cols):
	w = open(datadir + "/us/" + str(congressnumber) + "/stats/sponsorshipanalysis_" + house_or_senate + ".txt", "w")
	w.write("ID, ideology, leadership, name, party, description, introduced_bills_%d, cosponsored_bills_%d, unique_cosponsors_%d, total_cosponsors_%d\n" % tuple([congressnumber]*4))
	for i in xrange(nreps):
		w.write(", ".join( [unicode(d).encode("utf8") for d in
			[ids[i], spectrum[i], pagerank[i], names[i], parties[i], descr[i]] + other_cols[i]
			]) + "\n" )
	w.close()
	
def write_metadata_to_disk(congressnumber, house_or_senate, start_date, end_date):
	w = open(datadir + "/us/" + str(congressnumber) + "/stats/sponsorshipanalysis_" + house_or_senate + "_meta.txt", "w")
	w.write('{\n')
	w.write(' "start_date": "' + start_date + '",\n')
	w.write(' "end_date": "' + end_date + '"\n')
	w.write('}\n')
	w.close()

def create_member_images():
		# We no longer need this as the site displays Javascript-based graphs. So this is here
		# archivally and is no longer used.

		# Create an image for each person.
		for j in xrange(nreps):
			fig = plt.figure()
			plt.xlabel("Ideology", size="x-large") # size not working, ugh
			plt.ylabel("Leadership", size="x-large")
			plt.xticks([])
			plt.yticks([])	
			for party, color in (("Republican", "r"), ("Democrat", "b"), ("Independent", "k")):
				ss = [spectrum[i] for i in xrange(nreps) if parties[i] == party]
				pp = [pagerank[i] for i in xrange(nreps) if parties[i] == party]
				plt.plot(ss, pp, "." + color, markersize=7)
			plt.plot(spectrum[j], pagerank[j], "ok", markersize=20)
			plt.savefig(datadir + "/us/" + str(congressnumber) + "/stats/person/sponsorshipanalysis/" + str(ids[j]) + ".png", dpi=25, bbox_inches="tight", pad_inches=.05)

def do_analysis(congressnumber, starting_congress, house_or_senate, people, people_list):
	start_date, end_date, rep_to_row, nreps, P = build_matrix(congressnumber, starting_congress, house_or_senate, people, people_list)
	smooth_matrix(nreps, P)
	parties = build_party_list(rep_to_row, people, nreps)
	spectrum = ideology_analysis(nreps, parties, P)
	pagerank = leadership_analysis(nreps, P)
	ids, names, other_cols = build_output_columns(rep_to_row, people)
	draw_figure(congressnumber, house_or_senate, start_date, end_date, nreps, parties, spectrum, pagerank, names)
	descr = describe_members(nreps, parties, spectrum, pagerank)
	write_stats_to_disk(congressnumber, house_or_senate, nreps, ids, parties, names, spectrum, pagerank, descr, other_cols)
	write_metadata_to_disk(congressnumber, house_or_senate, start_date, end_date)

def influence_matrix(congressnumber, starting_congress, house_or_senate, people, people_list, sponsor):
	start_date, end_date, rep_to_row, nreps, P_initial = build_matrix(congressnumber, starting_congress, house_or_senate, people, people_list)
	parties = build_party_list(rep_to_row, people, nreps)
	initial_score = None
	initial_pctile = None
	for cosponsor in [None] + list(rep_to_row):
		P = numpy.array(P_initial) # clone
		if cosponsor != None: # baseline
			#P[(rep_to_row[sponsor], rep_to_row[cosponsor])] += 1
			P[(rep_to_row[cosponsor], rep_to_row[sponsor])] += 1
		smooth_matrix(nreps, P)
		spectrum = ideology_analysis(nreps, parties, P)
		score = spectrum[rep_to_row[sponsor]]
		pctile = scipy.stats.percentileofscore([spectrum[i] for i in range(nreps) if parties[i] == "Democrat"], score)
		if cosponsor is None:
			initial_score = score
			initial_pctile = pctile
			continue
		print sponsor, cosponsor, score - initial_score, pctile - initial_pctile
			
if __name__ == "__main__":
	congressnumber = int(sys.argv[1])

	# Who should we include in the analysis?
	people, people_list = get_people(get_roles_of_people(congressnumber))

	if len(sys.argv) == 3:
		influence_matrix(congressnumber, congressnumber-2, 'h', people, people_list, int(sys.argv[2]))
		sys.exit(0)

	# Auxiliary stats to include in output.
	for person_role in people.values():
		attach_other_stats(congressnumber, person_role)

	# Perform analysis totally separately for each chamber.
	os.system("mkdir -p " + datadir + "/us/" + str(congressnumber) + "/stats/person/sponsorshipanalysis")
	for house_or_senate in ('h', 's'):
		do_analysis(congressnumber, congressnumber-2, house_or_senate, people, people_list)


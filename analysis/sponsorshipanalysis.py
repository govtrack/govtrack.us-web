# Compute a Markov transition matrix representing the cosponsorship patterns
# of representatives and (separately) senators for a given (session of) Congress.
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

import sys
import os
import glob
import math
import numpy
import scipy.stats
import lxml.etree as lxml

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# CONFIGURATION

congressnumber = int(sys.argv[1])
datadir = "../data"
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

os.system("mkdir -p " + datadir + "/us/" + str(congressnumber) + "/stats/person/sponsorshipanalysis")

# Load up the session people file. We'll need some of this info later.
people = { }
peoplexml = lxml.parse(datadir + "/us/" + str(congressnumber) + "/people.xml")
for person in peoplexml.xpath("person"):
	people[int(person.get('id'))] = person

start_date = None
end_date = None

# Perform analysis totally separately for each chamber.
for house_or_senate in ('h', 's'):
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
	for cn in xrange(congressnumber-2, congressnumber+1):
		for billfilename in glob.glob(datadir + "/us/" + str(cn) + "/bills/" + house_or_senate + "*.xml"):
			xml = lxml.parse(billfilename)
			date = xml.xpath("introduced/@datetime")[0]
			start_date = min(start_date, date) if start_date else date
			end_date = max(end_date, date)
			
			spx = xml.xpath("sponsor/@id")
			if len(spx) == 0: # e.g. debt limit with no sponsor
				continue
			if not int(spx[0]) in people:
				continue
			sponsor = rownum(int(spx[0]))
			for cosponsor_str in xml.xpath("cosponsors/cosponsor/@id"):
				if not int(cosponsor_str) in people:
					continue
				cosponsor = rownum(int(cosponsor_str))
				cells.append( (sponsor, cosponsor) )
	
	# In the event a member of congress neither sponsored nor cosponsored
	# a bill, just give them an empty slot.
	tp = "rep" if house_or_senate == "h" else "sen"
	for person in peoplexml.xpath("person[role[@type='" + tp + "']]"):
		rownum(int(person.get('id')))

	# Get total number of members of congress seen.
	nreps = len(rep_to_row)
	
	# Turn this into a dense numpy array with cells flagged as 1 if there is such
	# a transition. Keep adding 1s... Start with the identity matrix because
	# every rep should be counted as sponsoring his own bills.
	P = numpy.identity(nreps, numpy.float) # numpy.zeros( (nreps,nreps) )
	for sponsor, cosponsor in cells:
		P[sponsor, cosponsor] += 1.0
	
	# Take the square root of each cell to flatten out outliers where one person
	# cosponsors a lot of other people's bills.
	for i in xrange(nreps):
		for j in xrange(nreps):
			P[i,j] = math.sqrt(P[i,j])

	
	# Political Spectrum Analysis
	#################

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
	parties = [None for i in xrange(nreps)]
	for k, v in rep_to_row.items():
		parties[v] = people[k].xpath('string(role[last()]/@party)')
	R_scores = [spectrum[i] for i in xrange(nreps) if parties[i] == "Republican"]
	R_score_mean = sum(R_scores)/len(R_scores)
	spectrum = spectrum * R_score_mean
	
	# third dimension of the analysis
	spectrum2 = vh[2,:]
	
	# "PageRank" Leadership
	###############

	# For each column, normalize so the sum is one.... or zero if this representative
	# didn't cosponsor anyone else's bills. That gets fixed later.
	for col in xrange(nreps):
		s = sum(P[:,col])
		if s > 0:
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
		
	pagerank = x
	
	# Output
	######
	
	# Create a list of names in row order.
	ids = [None for k in rep_to_row]
	names = [None for k in rep_to_row]
	usednames = { }
	for k, v in rep_to_row.items():
		ids[v] = k
		names[v] = people[k].get('lastname')
		
		# Check that the name is not a dup of someone else, and if so,
		# append a state (and district) to each.
		if names[v] in usednames:
			k2 = usednames[names[v]]
			
			names[v] = people[k].get('lastname') + " [" + people[k].xpath('string(role[@current]/@state)')  + people[k].xpath('string(role[@current]/@district)') + "]"
			
			names[rep_to_row[k2]] = people[k2].get('lastname') + " [" + people[k2].xpath('string(role[@current]/@state)')  + people[k2].xpath('string(role[@current]/@district)') + "]"
		else:
			usednames[names[v]] = k
	
	# Scale the values from 0 to 1.
	spectrum = rescale(spectrum)
	pagerank = rescale(pagerank, log=True)
	
	# Descriptions (allocate).
	descr = list(spectrum)
	
	# Draw a figure.
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

	# Describe what kind of person each is....
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
				["far-left Democratic leader", "moderate Democratic leader", "centrist Democratic leader"],
				["far-left Democrat", "rank-and-file Democrat", "centrist Democrat"],
				["lonely far-left Democratic ", "moderate Democratic follower", "centrist Democratic follower"],
				]
		elif party == "Republican":
			descr_table = [
				["centrist Republican leader", "moderate Republican leader", "far-right Republican leader"],
				["centrist Republican", "rank-and-file Republican", "far-right Republican"],
				["centrist Republican follower ", "moderate Republican follower", "lonley far-right Republican follower"],
				]
				
		else:
			# for independents, score according to the whole chamber
			ss_20 = scipy.stats.scoreatpercentile(spectrum, 20)
			ss_80 = scipy.stats.scoreatpercentile(spectrum, 80)
			
			pp_20 = scipy.stats.scoreatpercentile(pagerank, 20)
			pp_80 = scipy.stats.scoreatpercentile(pagerank, 80)
			
			descr_table = [
				["left-leaning, Independent leader", "moderate Independent leader", "right-leaning Independent leader"],
				["left-leaning Independent", "centrist Independent", "right-leaning Independent"],
				["lonely, left-leaning Independent", "lonely, centrist Independent", "lonely, right-leaning Independent"],
				]
				
		for i in xrange(nreps):
			if parties[i] == party:
				descr[i] = descr_table[2 if pagerank[i] < pp_20 else 1 if pagerank[i] < pp_80 else 0][0 if spectrum[i] < ss_20 else 1 if spectrum[i] < ss_80 else 2]
		
	# Dump CSV file.
	
	w = open(datadir + "/us/" + str(congressnumber) + "/stats/sponsorshipanalysis_" + house_or_senate + ".txt", "w")
	w.write("ID, ideology, leadership, name, party, description, ideology2\n")
	for i in xrange(nreps):
		w.write(", ".join( [unicode(d).encode("utf8") for d in (ids[i], spectrum[i], pagerank[i], names[i], parties[i], descr[i], spectrum2[i])]) + "\n" )
	w.close()
	
	# Dump metadata JSON file.
	
	w = open(datadir + "/us/" + str(congressnumber) + "/stats/sponsorshipanalysis_" + house_or_senate + "_meta.txt", "w")
	w.write('{\n')
	w.write(' "start_date": "' + start_date + '",\n')
	w.write(' "end_date": "' + end_date + '"\n')
	w.write('}\n')
	w.close()

	# Create an image for each person.
	# We no longer need this as the site displays Javascript-based graphs.
	if False:
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
			

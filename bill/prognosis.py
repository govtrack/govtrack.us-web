#!script

# Compute the success rates of different types of bills with
# different prognosis factors.

import lxml, scipy.stats, numpy, itertools, re, csv
from logistic_regression import *

from bill.models import *
from committee.models import *
from person.models import *
from person.types import RoleType
from person.analysis import load_sponsorship_analysis
from us import get_congress_dates

from django.db.models import Count

# Group BillType types into bill, joint res, concurrent res, and simple res.
bill_type_map = {
	"bill": (BillType.house_bill, BillType.senate_bill),
	"jr": (BillType.house_joint_resolution, BillType.senate_joint_resolution),
	"cr": (BillType.house_concurrent_resolution, BillType.senate_concurrent_resolution),
	"sr": (BillType.house_resolution, BillType.senate_resolution),
}
bill_type_map_inv = { }
for k, v in bill_type_map.items():
	for bt in v:
		bill_type_map_inv[bt] = k
bill_type_names = {
	"bill": "bills",
	"jr": "joint resolutions",
	"cr": "concurrent resolutions",
	"sr": "simple resolutions",
}

def load_majority_party(congress):
	majority_party = { }
	start, end = get_congress_dates(congress)
	
	for rt, bts in (
		(RoleType.senator, (BillType.senate_bill, BillType.senate_resolution, BillType.senate_concurrent_resolution, BillType.senate_joint_resolution)),
		(RoleType.representative, (BillType.house_bill, BillType.house_resolution, BillType.house_concurrent_resolution, BillType.house_joint_resolution))
		):
		p = PersonRole.objects.filter(startdate__lte=end, enddate__gte=start, role_type=rt).values("party").annotate(count=Count("id")).order_by("-count")[0]["party"]
		for bt in bts:
			majority_party[bt] = p
	return majority_party

def load_committee_membership(congress):
	# load archival committee data for a given congress
	if congress >= 115: return { }
	from parser.committee_parser import ROLE_MAPPING
	committee_membership = { }
	for cnode in lxml.etree.parse("data/historical-committee-membership/%d.xml" % congress).xpath("committee|committee/subcommittee"):
		code = cnode.get("code")
		if cnode.tag == "subcommittee": code = cnode.getparent().get("code") + code # not working?
		for mnode in cnode.xpath("member"):
			id = int(mnode.get("id"))
			if not id in committee_membership: committee_membership[id] = { }
			committee_membership[id][code] = ROLE_MAPPING[mnode.get("role", "Member")]
	return committee_membership

cached_leadership_scores = { }
def get_leadership_score(person):
	if person.id in cached_leadership_scores: return cached_leadership_scores[person.id]
	sp_ana = load_sponsorship_analysis(person)
	score = float(sp_ana["leadership"]) if sp_ana else None
	cached_leadership_scores[person.id] = score
	return score

def load_lobbying_data(congress):
	return None # otherwise loading bill pages would invoke this and take a long time to load
	# Count up the number of ocurrences of each bill in the CRP lobbying database.
	from numpy import median
	bill_number_re = re.compile(r"^(hr?|s|hconres|hcon|sconres|scon|hjres|hj|sjres|sj|hres|sres|sr)(\d+)$", re.I)
	bill_type_special = { "h": "hr", "sr": "sres", "hj": "hjres", "sj": "sjres", "scon": "sconres", "hcon": "hconres" }
	lob_bills = csv.reader(open("../crp_lob_bills_20120408.txt"), quotechar="|")
	lobbying_data = { }
	for pk, isssue_id, bill_congress, bill_number in lob_bills:
		if bill_congress.strip() == "" or congress != int(bill_congress): continue
		if bill_number.replace(".", "").startswith("HAMDT"): continue
		if bill_number.replace(".", "").startswith("SAMDT"): continue
		m = bill_number_re.match(bill_number.strip().lower().replace(".", ""))
		if m == None:
			print "bad bill in lobbying data %s %s" % (bill_congress, bill_number)
		else:
			bt, bn = m.group(1), m.group(2)
			bt = bill_type_special.get(bt, bt)
			bt = BillType.by_slug(bt)
			bn = int(bn)
			lobbying_data[(bt, bn)] = lobbying_data.get((bt, bn), 0) + 1
	return { "median": median(lobbying_data.values()), "counts": lobbying_data }

def get_bill_factors(bill, pop_title_prefixes, committee_membership, majority_party, lobbying_data, include_related_bills=True):
	factors = list()
	
	# introduced date (idea from Yano, Smith and Wilkerson 2012 paper)
	idate = bill.introduced_date
	if hasattr(idate, 'date'): idate = idate.date() # not sure how this is possible
	if (idate - get_congress_dates(bill.congress)[0]).days < 90:
		factors.append(("introduced_first90days", "The %s was introduced in the first 90 days of the Congress." % bill.noun, "Introduced in the first 90 days of the Congress (incl. companion bills)."))
	if (idate - get_congress_dates(bill.congress)[0]).days < 365:
		factors.append(("introduced_firstyear", "The %s was introduced in the first year of the Congress." % bill.noun, "Introduced in the first year of the Congress (incl. companion bills)."))
	if (get_congress_dates(bill.congress)[1] - idate).days < 90:
		factors.append(("introduced_last90days", "The %s was introduced in the last 90 days of the Congress." % bill.noun, "Introduced in the last 90 days of the Congress (incl. companion bills)."))
	
	# does the bill's title start with a common prefix?
	for prefix in pop_title_prefixes:
		if bill.title_no_number.startswith(prefix + " "):
			factors.append(("startswith:" + prefix, "The %s's title starts with \"%s.\"" % (bill.noun, prefix), "Title starts with \"%s\"." % prefix))
	
	cosponsors = list(Cosponsor.objects.filter(bill=bill, withdrawn=None).select_related("person"))
	committees = list(bill.committees.all())
	
	maj_party = majority_party[bill.bill_type]
	
	if bill.sponsor_role:
		# party of the sponsor
		sponsor_party = bill.sponsor_role.party
		if sponsor_party != maj_party:
			factors.append( ("sponsor_minority", "The sponsor is a member of the minority party.", "Sponsor is a member of the minority party.") )
	
		# is the sponsor a member/chair of a committee to which the bill has
		# been referred?
		for rname, rvalue in (("member", CommitteeMemberRole.member), ("rankingmember", CommitteeMemberRole.ranking_member), ("chair", CommitteeMemberRole.vice_chair), ("chair", CommitteeMemberRole.chair)):
			for committee in committees:
				if committee_membership.get(bill.sponsor_id, {}).get(committee.code) == rvalue:
					if rvalue != CommitteeMemberRole.member:
						factors.append(("sponsor_committee_%s" % rname, "The sponsor is the %s of a committee to which the %s has been referred." % (CommitteeMemberRole.by_value(rvalue).label.lower(), bill.noun), "Sponsor is a relevant committee %s." % CommitteeMemberRole.by_value(rvalue).label.lower()))
					elif sponsor_party == maj_party:
						factors.append(("sponsor_committee_member_majority", "The sponsor is on a committee to which the %s has been referred, and the sponsor is a member of the majority party." % bill.noun, "Sponsor is on a relevant committee & in majority party."))
						
		# leadership score of the sponsor, doesn't actually seem to be helpful,
		# even though leadership score of cosponsors is.
		if get_leadership_score(bill.sponsor) > .8:
			if sponsor_party == maj_party:
				factors.append(("sponsor_leader_majority", "The sponsor is in the majority party and has a high leadership score.", "Sponsor has a high leadership score (majority party)."))
			else:
				factors.append(("sponsor_leader_minority", "The sponsor has a high leadership score but is not in the majority party.", "Sponsor has a high leadership score (minority party)."))
					
	# count cosponsor assignments to committees by committee role and Member party
	for rname, rvalue in (("committeemember", CommitteeMemberRole.member), ("rankingmember", CommitteeMemberRole.ranking_member), ("chair", CommitteeMemberRole.vice_chair), ("chair", CommitteeMemberRole.chair)):
		num_cosp = 0
		for cosponsor in cosponsors:
			for committee in committees:
				cvalue = committee_membership.get(cosponsor.person.id, {}).get(committee.code)
				if cvalue == rvalue or (rvalue==CommitteeMemberRole.member and cvalue != None):
					num_cosp += 1
					break
		if rvalue == CommitteeMemberRole.member:
			if num_cosp >= 2:
				factors.append( ("cosponsors_%s", "At least two cosponsors serve on a committee to which the %s has been referred." % (bill.noun,), "2 or more cosponsors are on a relevant committee.") )
		elif num_cosp > 0:
			rname2 = CommitteeMemberRole.by_value(rvalue).label.lower()
			factors.append( ("cosponsor_%s" % rname, "A cosponsor is the %s of a committee to which the %s has been referred." % (rname2, bill.noun), "A cosponsor is a relevant committee %s." % rname2))
			
	# what committees is the bill assigned to? only look at committees
	# in the originating chamber, since assignments in the other chamber
	# indicate the bill had at least one successful vote.
	for cm in committees:
		if cm.committee != None: continue # skip subcommittees
		if CommitteeType.by_value(cm.committee_type).label != bill.originating_chamber: continue
		factors.append( ("committee_%s" % cm.code, "The bill was referred to %s." % cm.shortname, "Referred to %s (incl. companion)." % cm.shortname))

	# do we have cosponsors on both parties?
	num_cosp_majority = 0
	for cosponsor in cosponsors:
		if cosponsor.role.party == maj_party:
			num_cosp_majority += 1
	if bill.sponsor and sponsor_party == maj_party and len(cosponsors) >= 6 and num_cosp_majority < 2.0*len(cosponsors)/3:
		factors.append(("cosponsors_bipartisan", "The sponsor is in the majority party and at least one third of the %s's cosponsors are from the minority party." % bill.noun, "Sponsor is in majority party and 1/3rd+ of cosponsors are in minority party."))
	elif num_cosp_majority > 0 and num_cosp_majority < len(cosponsors):
		factors.append(("cosponsors_crosspartisan", "There is at least one cosponsor from the majority party and one cosponsor outside of the majority party.", "Has cosponsors from both parties."))

	for is_majority in (False, True):
		for cosponsor in cosponsors:
			if (cosponsor.role.party == maj_party) != is_majority: continue
			if get_leadership_score(cosponsor.person) > .85:
				if is_majority:
					factors.append(("cosponsor_leader_majority", "A cosponsor in the majority party has a high leadership score.", "Cosponsor has high leadership score (majority party)."))
				else:
					factors.append(("cosponsor_leader_minority", "A cosponsor in the minority party has a high leadership score.", "Cosponsor has high leadership score (minority party)."))
				break

	# Is this bill a re-intro from last Congress, and if so was that bill reported by committee?
	if bill.sponsor:
		def normalize_title(title):
			# remove anything that looks like a year
			return re.sub(r"of \d\d\d\d$", "", title)
		for reintro in Bill.objects.filter(congress=bill.congress-1, sponsor=bill.sponsor):
			if normalize_title(bill.title_no_number) == normalize_title(reintro.title_no_number):
				if reintro.current_status != BillStatus.introduced:
					factors.append(("reintroduced_of_reported", "This %s was reported by committee as %s in the previous session of Congress." % (bill.noun, reintro.display_number), "Got past committee in a previous Congress."))
				else:
					factors.append(("reintroduced", "This %s was a re-introduction of %s from the previous session of Congress." % (bill.noun, reintro.display_number), "Is a bill reintroduced from a previous Congress."))
				break

	if include_related_bills: # prevent infinite recursion
		# Add factors from any CRS-identified identical bill, changing most factors'
		# key into companion_KEY so that they become separate factors to consider.
		# For some specific factors, lump them in with the factor for the bill itself.
		for rb in RelatedBill.objects.filter(bill=bill, relation="identical").select_related("related_bill", "related_bill__sponsor_role"):
			# has a companion
			factors.append(("companion", "The %s has been introduced in both chambers (the other is %s)." % (bill.noun, rb.related_bill.display_number), "Has a companion bill in the other chamber."))
			
			# companion sponsor's party
			if bill.sponsor_role and rb.related_bill.sponsor_role:
				if bill.sponsor_role.party != rb.related_bill.sponsor_role.party:
					factors.append(("companion_bipartisan", "The %s's companion %s was sponsored by a member of the other party." % (bill.noun, rb.related_bill.display_number), "Has a companion bill sponsored by a member of the other party."))
			
			for f in get_bill_factors(rb.related_bill, pop_title_prefixes, committee_membership, majority_party, lobbying_data, include_related_bills=False):
				if "startswith" in f[0]: continue # don't include title factors because the title is probs the same
				if f[0] in ("introduced_first90days", "introduced_last90days", "introduced_firstyear", "reintroduced_of_reported", "reintroduced") or f[0].startswith("committee_"):
					f = (f[0], "%s (on companion bill %s)" % (f[1], rb.related_bill.display_number), f[2])
				else:
					f = ("companion__" + f[0], "Companion bill " + rb.related_bill.display_number + ": " + f[1], "On a companion bill: " + f[2])
					
				# Make sure not to duplicate any factors, especially if we are promoting the companion
				# bill factor to a main factor, we don't want to double count or override the description
				# on the main bill.
				if f[0] in set(k[0] for k in factors): continue
				
				factors.append(f)

	# Are lobbyists registering that they are lobbying on this bill? Does this bill
	# have more registered lobbying than the median bill? Overall this picks out
	# bills NOT likely to be enacted.
	#	
	# Two possible explanations: First, lobbying can be to defeat a bill not just
	# pass it. So this would indicate that on balance lobbying is having that effect.
	#
	# Second it could be because lobbyists don't bother with
	# the easy bills that don't need their help. Meaning, they pick out a pool of
	# improbable bllls, and presumably make those bills more likely to be enacted
	# but still not as likely as the easy bills. (If they truly hurt a bill's future, they
	# would presumably know and stop lobbying!)
	#
	# Looking at lobbying might be more useful if we combined it with another
	# factor that could pick out the hard bills, and then this might show that for
	# hard bills, lobbying made the bills more successful. But it's a bit impossible
	# because surely the lobbyists know better than we do which bills are hard,
	# so it would be impossible to factor out "hard bills" entirely.
	if False:
		if lobbying_data["counts"].get( (bill.bill_type, bill.number), 0 ) > lobbying_data["median"]:
			factors.append( ("crp-lobby-many", "The Center for Responsive Politics reports that a large number of organizations are lobbying on this %s." % bill.noun, "Has many lobbyists.") )
		elif lobbying_data["counts"].get( (bill.bill_type, bill.number), 0 ) > 0:
			factors.append( ("crp-lobby", "The Center for Responsive Politics reports that organizations are lobbying on this %s." % bill.noun, "Has lobbyists.") )

	return factors

def is_success(bill, model_type, indexed_paragraphs):
	# ok I think I got lucky that numpy.array turns True/False into 1.0/0.0
	if model_type == 0:
		return bill.current_status != BillStatus.introduced
	else:
		if bill.current_status in BillStatus.final_status_passed:
			return 1.0

		# If the bill wasn't itself enacted, compare its contents to
		# enacted bills.
		hashes = get_bill_paragraphs(bill)
		if not hashes: return 0.0 # text not available
		good_hashes = 0.0
		total_hashes = 0.0
		for h in hashes:
			c = indexed_paragraphs.get(h, 0)
			if c > 1: continue # if it occurs more than once in enacted bills, it's probably boilerplate so skip it
			total_hashes += 1.0
			if c == 1: good_hashes += 1.0
		return good_hashes/total_hashes
					
def build_model(congress):
	majority_party = load_majority_party(congress)
	committee_membership = load_committee_membership(congress)
	indexed_success_text = load_indexed_success_text()
	lobbying_data = None #load_lobbying_data(congress)
	
	# universe
	BILLS = Bill.objects.filter(congress=congress).prefetch_related()
	
	# compute the most frequent first few words of bills. slurp in all of the titles,
	# record the counts of all of the prefixes of the titles, and then take the top few,
	# excluding ones that are prefixes of another popular prefix.
	title_counts = { }
	for bill in BILLS:
		title = bill.title_no_number
		if title.startswith("Providing for consideration of"): continue # hack, add later
		for nwords in xrange(4, 10):
			prefix = " ".join(title.split(" ")[0:nwords])
			title_counts[prefix] = title_counts.get(prefix, 0) + 1
	title_counts = sorted(title_counts.items(), key = lambda kv : kv[1], reverse=True)
	pop_title_prefixes = list()
	for t, c in title_counts:
		seen = False
		for tt in list(pop_title_prefixes):
			if tt.startswith(t + " "):
				seen = True
			elif t.startswith(tt + " "):
				pop_title_prefixes.remove(tt)
		if seen: continue
		pop_title_prefixes.append(t)
		if len(pop_title_prefixes) == 40: break
	pop_title_prefixes.append("A joint resolution proposing an amendment to the Constitution")
	pop_title_prefixes.append("Providing for consideration of")
		
	# We create separate models for bills by the bill type (bill, joint resolution,
	# concurrent resolution, simple resolution) and by whether the bill's status is
	# introduced or has been reported or more.
	#
	# Once a bill has been reported by committee it's chances of success are
	# of course much higher, since the bills that have not been reported by committee
	# in historical data are necessarily failed bills. Also the models change
	# substantially.
		
	MODEL = dict()
	
	for bill_type, model_type in itertools.product(bill_type_map.keys(), (0, 1)):
		# GET LIST OF BILLS
		
		bills = BILLS.filter(bill_type__in=bill_type_map[bill_type])
		if model_type == 1:
			# In model 0, we scan across all bills, because all bills were
			# in the introduced status at one point. If we filter it to bills whose
			# current status is introduced, obviously they will all have been
			# failed bills, which defeats the purpose. In model 1, we
			# only look at bills that have at least gotten reported so that we can see
			# of reported bills which make it to success.
			bills = bills.exclude(current_status=BillStatus.introduced)

		print bill_type, model_type
		
		total = bills.count()
		
		if model_type == 0:
			# for the introduced model, success is getting out of committee
			total_success = bills.exclude(current_status=BillStatus.introduced).count()
		else:
			# for the reported model, success is being enacted (or whatever final status as appropriate for the bill type)
			total_success = bills.filter(current_status__in=BillStatus.final_status_passed).count()
			
		print "\toverall", int(round(100.0*total_success/total)), "%; N=", total
		
		# GET REGRESSION MATRIX INFORMATION
		
		# Build a list of sets, one for each bill, containing the binary
		# factors that apply to the bill. Build a corresponding list of
		# floats (either 1.0, 0.0) indicating whether the bill was successful.
		#
		# Also remember for each binary factor the total count of bills
		# it applied to and the count of those that were successful.
		#
		# And also remember for each binary factor, the short descriptive
		# text for the factor.
		
		factor_success_rate = { }
		regression_outcomes = [ ]
		regression_predictors = [ ]
		factor_descriptions = { }
		#bills = bills[0:100] # REMOVEME
		for bill in bills:
			# What's the measured outcome for this bill? Check if the bill
			# ended in a success state. Allow floating-point values!
			success = is_success(bill, model_type, indexed_success_text[bill_type])
			
			# Get the binary factors that apply to this bill.
			factors = get_bill_factors(bill, pop_title_prefixes, committee_membership, majority_party, lobbying_data)
			
			# maintain a simple list of success percent rates for each factor individually
			for key, descr, general_descr in factors:
				if not key in factor_success_rate: factor_success_rate[key] = [0, 0] # count of total, successful
				factor_success_rate[key][0] += 1
				factor_success_rate[key][1] += success
				factor_descriptions[key] = general_descr
				
			# build data for a regression
			regression_outcomes.append(success)
			regression_predictors.append(set( f[0] for f in factors )) # extract just the key from the (key, descr) tuple
			
		# FIRST PASS SIGNIFICANCE CHECK
		
		# Reduce the complexity of the regression model by filtering out
		# factors that, when considered independently, don't have a success
		# rate that appears to differ from the population success rate.
			
		factor_binomial_sig = dict()
		for key, bill_counts in factor_success_rate.items():
			# If there were very few bills with this factor, do not include it in the model.
			if bill_counts[0] < 15: continue
			
			# Create a binomial distribution with a sample size the same as
			# the number of bills with this factor, and with a probability
			# of heads equal to the population success rate.
			distr = scipy.stats.binom(bill_counts[0], float(total_success)/float(total))
			
			# What is the possibility that we would see as many or as few
			# successes as we do (i.e. two tailed).
			pless = distr.cdf(bill_counts[1]) # as few == P(count <= observed)
			pmore = 1.0-(distr.cdf(bill_counts[1]-1) if bill_counts[1] > 0 else 0.0) # as many == P(count >= observed)
			p = min(pless, pmore)
			if p < .05:
				factor_binomial_sig[key] = p
				
		# LOGISTIC REGRESSION
		
		for trial in xrange(2):
			regression_predictors_map = None
			regression_beta = None
			if len(factor_binomial_sig) > 0:
				# Assign consecutive indices to the remaining factors.
				regression_predictors_map = dict(reversed(e) for e in enumerate(factor_binomial_sig))
				
				# Build a binary matrix indicating which bills have which factors.
				regression_predictors_2 = [ [] for f in regression_predictors_map ]
				for factors in regression_predictors:
					for fname, findex in regression_predictors_map.items():
						regression_predictors_2[findex].append(1.0 if fname in factors else 0.0)
				regression_predictors_2 = numpy.array(regression_predictors_2)
				regression_outcomes = numpy.array(regression_outcomes)
				
				# Perform regression.
				regression_beta, J_bar, l = logistic_regression(regression_predictors_2, regression_outcomes)
				
				# Remove factors that are within 1.75 standard error from zero,
				# and then re-run the regression.
				if trial == 0:
					# Get the standard errors (the logistic_regression module
					# says to do it this way).
					from numpy import sqrt, diag, abs, median
					from numpy.linalg import inv
					try:
						stderrs = sqrt(diag(inv(J_bar))) # [intercept, beta1, beta2, ...]
					except numpy.linalg.linalg.LinAlgError as e:
						print "\t", e
						break
					
					# The standard errors are coming back wacky large for
					# the factors with VERY large beta. Special-case those.
					for fname, findex in regression_predictors_map.items():
						beta = regression_beta[findex+1]
						stderr = stderrs[findex+1]
						if abs(beta/stderr) < 1.75 and abs(beta) < 5.0:
							# This factor's effect is small/non-significant,
							# so remove it from factor_binomial_sig so that on
							# next iteration it is excluded from regression.
							del factor_binomial_sig[fname]
			
		# Generate the model for output.
		model = dict()
		MODEL[(bill_type,model_type == 0)] = model
		if model_type == 0:
			model["success_name"] = "sent out of committee to the floor"
		else:
			if bill_type == "bill":
				model["success_name"] = "enacted"
			elif bill_type == "jr":
				model["success_name"] = "enacted or passed"
			else:
				model["success_name"] = "agreed to"
		model["count"] = total
		model["success_rate"] = 100.0*total_success/total
		model["bill_type"] = bill_type
		model["bill_type_descr"] = bill_type_names[bill_type]
		model["is_introduced_model"] = (model_type == 0)
		model["regression_predictors_map"] = regression_predictors_map
		model["regression_beta"] = list(regression_beta) if regression_beta != None else None
		model_factors = dict()
		model["factors"] = model_factors
		for key, bill_counts in factor_success_rate.items():
			if key not in factor_binomial_sig: continue
			print "\t" + key, \
				int(round(100.0*bill_counts[1]/bill_counts[0])), "%;", \
				"N=", bill_counts[0], \
				"p<", int(round(100*factor_binomial_sig[key])), \
				"B=", regression_beta[regression_predictors_map[key]+1]
			model_factors[key] = dict()
			model_factors[key]["count"] = bill_counts[0]
			model_factors[key]["success_rate"] = 100.0*bill_counts[1]/bill_counts[0]
			model_factors[key]["regression_beta"] = regression_beta[regression_predictors_map[key]+1]
			model_factors[key]["description"] = factor_descriptions[key]
			
	with open("bill/prognosis_model.py", "w") as modelfile:
		modelfile.write("# this file was automatically generated by prognosis.py\n")
		modelfile.write("congress = %d\n" % congress)
		from pprint import pprint
		modelfile.write("pop_title_prefixes = ")
		pprint(pop_title_prefixes, modelfile)
		modelfile.write("factors = ")
		pprint(MODEL, modelfile)

def compute_prognosis_2(prognosis_model, bill, committee_membership, majority_party, lobbying_data, proscore=False, testing=False):
	# get a list of (factorkey, descr) tuples of the factors that are true for
	# this bill. use the model to convert these tuples into %'s and descr's.
	factors = get_bill_factors(bill, prognosis_model.pop_title_prefixes, committee_membership, majority_party, lobbying_data)
	
	# There are two models for every bill, one from introduced to reported
	# and the other from reported to success.
	
	model_1 = prognosis_model.factors[(bill_type_map_inv[bill.bill_type], True)]
	model_2 = prognosis_model.factors[(bill_type_map_inv[bill.bill_type], False)]
	
	# Eliminate factors that are not used in either model.
	factors = [f for f in factors if f[0] in model_1["factors"] or f[0] in model_2["factors"]]
	
	# If we are doing a "proscore", remove any startswith factors that increase
	# a bill's prognosis. These are usually indicative of boring bills like renaming a
	# post office. Startswith factors that decrease a bill's prognosis are still good
	# to include.
	if proscore:
		factors = [(key, decr, longdescr) for (key, decr, longdescr) in factors if 
			not key.startswith("startswith:")
			or (key in model_1["factors"] and model_1["factors"][key]["regression_beta"] < 0)
			or (key in model_2["factors"] and model_2["factors"][key]["regression_beta"] < 0)]

	def eval_model(model):
		# make a prediction using the logistic regression model
		if model["regression_beta"] == None:
			return model["success_rate"]
		else:
			factor_keys = set(f[0] for f in factors)
			predictors = [0.0 for f in xrange(len(model["regression_beta"])-1)] # remove the intercept
			for key, index in model["regression_predictors_map"].items():
				predictors[index] = 1.0 if key in factor_keys else 0.0
			return float(calcprob(model["regression_beta"], numpy.transpose(numpy.array([predictors]))))
			
	prediction_1 = eval_model(model_1)
	prediction_2 = eval_model(model_2)
	
	is_introduced = bill.current_status == BillStatus.introduced
	
	def helps(factor, state1, state2):
		a = model_1["factors"][factor]["regression_beta"] >= 0 if factor in model_1["factors"] else model_2["factors"][factor]["regression_beta"] >= 0
		b = model_2["factors"][factor]["regression_beta"] >= 0 if factor in model_2["factors"] else model_1["factors"][factor]["regression_beta"] >= 0
		return (a==state1) and (b==state2)
	
	return {
		"is_introduced": is_introduced,
		
		"success_name_1": model_1["success_name"],
		"success_name_2": model_2["success_name"],
		"success_rate_1": model_1["success_rate"],
		"success_rate_2": model_2["success_rate"],
		"success_rate": model_1["success_rate"] * model_2["success_rate"] / 100.0,
		
		"prediction_1": prediction_1,
		"prediction_2": prediction_2,
		"prediction": (prediction_1 * prediction_2 / 100.0) if is_introduced or testing else prediction_2,
		"success_name": model_2["success_name"],
		"bill_type_descr": model_2["bill_type_descr"],
		
		"factors_help_help": [descr for key, descr, gen_descr in factors if helps(key, True, True)],
		"factors_hurt_hurt": [descr for key, descr, gen_descr in factors if helps(key, False, False)],
		"factors_help_hurt": [descr for key, descr, gen_descr in factors if helps(key, True, False)],
		"factors_hurt_help": [descr for key, descr, gen_descr in factors if helps(key, False, True)],
	}

def compute_prognosis(bill, proscore=False):
	import prognosis_model
	majority_party = load_majority_party(bill.congress)
	committee_membership = load_committee_membership(bill.congress)
	prog = compute_prognosis_2(prognosis_model, bill, committee_membership, majority_party, None, proscore=proscore)
	prog["congress"] = prognosis_model.congress
	return prog
		
def test_prognosis(congress):
	from math import exp
	from numpy import mean, median, std, digitize, percentile, average
	
	from bill import prognosis_model_112 as prognosis_model
	
	majority_party = load_majority_party(congress)
	committee_membership = load_committee_membership(congress)
	indexed_success_text = load_indexed_success_text()
	
	test_results = { }
	
	for model_type in (0, 1):
		for bt in bill_type_map:
			print "Testing", model_type, bt, "..."
			
			# What was the success rate in the training data?
			model = prognosis_model.factors[(bt, model_type==0)]
			sr = model["success_rate"]
			if len(model["factors"]) == 0: continue # nothing interesting to test
			
			# store output....
			model_result = { }
			test_results[(bt, model_type)] = model_result
			model_result["overall"] = sr
			
			for key in ("bill_type", "bill_type_descr", "is_introduced_model", "success_name"):
				model_result[key] = model[key]
			
			# Pull in the data as tuples of (prediction, success), each of which is a
			# float in the range of [0,1].
			bills = Bill.objects.filter(congress=congress, bill_type__in=bill_type_map[bt])
			if model_type == 1: bills = bills.exclude(current_status=BillStatus.introduced)
			#bills = bills[0:100] # REMOVEME
			model_result["count"] = bills.count()
			data = []
			for bill in bills.prefetch_related():
				x = compute_prognosis_2(prognosis_model, bill, committee_membership, majority_party, None, proscore=False, testing=True)
				if model_type == 0:
					x = x["prediction_1"]
				else:
					x = x["prediction_2"]
				y = is_success(bill, model_type, indexed_success_text[bt])
				data.append((x, y))
			xdata = [x[0] for x in data]
			
			# Compute %-success for bins each having 10% of the data, to show that as
			# prognosis increases, the %-success increases.
			model_result["bins"] = []
			bins = []
			for p in xrange(0, 100+10, 10):
				b = percentile(xdata, p)
				if len(bins) == 0 or b > bins[-1]:
					bins.append(b)
			bindices = digitize(xdata, bins)
			for b in xrange(len(bins)-1):
				bindata = [data[i] for i in xrange(len(data)) if bindices[i] == b]
				if len(bindata) == 0: continue
				median_prog = median([x for x,y in bindata])
				pct_success = mean([y for x,y in bindata])
				model_result["bins"].append( (median_prog, len(bindata), pct_success) )
			
			# Make a precision-recall chart over various values for a prognosis threshold.
			# This chart doesn't make much sense now that we measure success as a
			# continuous variable. I've adapted the notions of precision and recall so
			# that they are sensible in this case. When the y values are in fact binary
			# (0.0 or 1.0), the result is the traditional definition of precision and
			# recall.
			def compute_scores(T):
				precision = mean([y for (x,y) in data if (x >= T)])
				recall = average([1.0 if x >= T else 0.0 for (x,y) in data], weights=[y for (x,y) in data])
				return {
					"threshold": T,
					"precision": precision,
					"recall": recall,
				}
			model_result["precision_recall"] = []
			for i in range(-18, 0):
				T = 100 * exp(i / 5.0) # threshold data points on a logarithmic scale
				cs = compute_scores(T)
				if cs["precision"]+cs["recall"] == 0: continue # causes weirdness in charts
				model_result["precision_recall"].append(cs)
			

	with open("bill/prognosis_model_test.py", "w") as modelfile:
		modelfile.write("# this file was automatically generated by prognosis.py\n")
		modelfile.write("train_congress = %d\n" % prognosis_model.congress)
		modelfile.write("test_congress = %d\n" % congress)
		from pprint import pprint
		modelfile.write("model_test_results = ")
		pprint(test_results, modelfile)

def top_prognosis(congress, bill_type):
	max_p = None
	max_b = None
	majority_party = load_majority_party(congress)
	committee_membership = load_committee_membership(congress)
	for bill in Bill.objects.filter(congress=congress, bill_type__in=bill_type_map_inv[bill_type]):
		p = compute_prognosis_2(bill, committee_membership, majority_party)
		if not max_p or p["prediction"] > max_p:
			max_p = p["prediction"]
			max_b = bill
	print max_p, max_b

def get_bill_paragraphs(bill):
	import lxml.html
	from bill.billtext import load_bill_text
	from hashlib import md5
		
	try:
		dom = lxml.html.fromstring(load_bill_text(bill, None)["text_html"])
	except IOError:
		print("no bill text", bill.id, bill)
		return None
	except Exception as e:
		print("error in bill text", bill.id, bill, e)
		return None
		
	hashes = { }
		
	for node in dom.xpath("//p"):	
		text = lxml.etree.tostring(node, method="text", encoding="utf8")
		text = text.lower() # normalize case
		text = re.sub("^\(.*?\)\s*", "", text) # remove initial list numbering
		text = re.sub(r"\W+", " ", text).strip() # normalize spaces and other non-word characters
		if text == "": continue
		text = md5(text).hexdigest()
		hashes[text] = hashes.get(text, 0) + 1

	return hashes

def index_successful_paragraphs(congress, fn='prognosis_model_paragraphs.txt'):
	cache = { bt: {} for bt in bill_type_map }
		
	# For each successful bill, load its text and store hashes of
	# its paragraphs.
	for bill_type in bill_type_map.keys():
		bills = Bill.objects.filter(congress=congress, bill_type__in=bill_type_map[bill_type],
			current_status__in=BillStatus.final_status_passed)
		for bill in bills:
			hashes = get_bill_paragraphs(bill)
			if not hashes: continue
			for h, c in hashes.items():
				cache[bill_type][h] = cache[bill_type].get(h, 0) + c

	# Write out a list of hashes and for each, the number of times
	# the hash occurred in successful bills. Paragraphs that appear
	# more than once won't be counted.
	with open("bill/" + fn, "w") as cachefile:
		for bill_type in bill_type_map.keys():
			cachefile.write(bill_type + "\n")
			for k, v in sorted(cache[bill_type].items()):
				cachefile.write(k + " " + str(v) + "\n")
			cachefile.write("\n")
		
def load_indexed_success_text(fn='prognosis_model_paragraphs.txt'):
	cache = { bt: {} for bt in bill_type_map } 
	bt = None
	with open("bill/" + fn) as cachefile:
		for line in cachefile:
			line = line.strip()
			if bt is None:
				bt = line
			elif line == "":
				bt = None # next line is a bill type
			else:
				hashval, count = line.split(" ")
				cache[bt][hashval] = int(count)
	return cache

def dump_prognosis(congress):
	import csv, tqdm
	from bill import prognosis_model_112 as prognosis_model

	majority_party = load_majority_party(congress)
	committee_membership = load_committee_membership(congress)
	index_successful_paragraphs(congress, 'prognosis-test-text.txt')
	indexed_success_text = load_indexed_success_text('prognosis-test-text.txt')

	w = csv.writer(open("prognosis-dump.csv", "w"))
	w.writerow(["bill_type", "model0prediction", "prediction", "model0actual", "actual_a", "actual", "bill_id", "bill"])

	bills = Bill.objects.filter(congress=congress)
	for bill in tqdm.tqdm(bills.prefetch_related()):
             # set testing=True to not allow use of current_status
		x = compute_prognosis_2(prognosis_model, bill, committee_membership, majority_party, None, proscore=False, testing=False)
		y0 = is_success(bill, 0, indexed_success_text[bill_type_map_inv[bill.bill_type]])
		y1 = is_success(bill, 1, indexed_success_text[bill_type_map_inv[bill.bill_type]])
		y2 = "-" # (bill.was_enacted_ex() is not None)
		w.writerow([bill_type_map_inv[bill.bill_type], x["prediction_1"], x["prediction"], y0, y1, y2, bill.id, bill.congressproject_id])
			
if __name__ == "__main__":
	import sys
	if sys.argv[-1] == "train":
		index_successful_paragraphs(113)
		build_model(113)
	elif sys.argv[-1] == "test":
		#index_successful_paragraphs(112)
		#build_model(112) # delete the model after if this is for a past Congress!
		index_successful_paragraphs(113)
		test_prognosis(113)
	elif sys.argv[-1] == "index-text":
		index_successful_paragraphs(114)
	elif sys.argv[-1] == "dump":
		dump_prognosis(114)

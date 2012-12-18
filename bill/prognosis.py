#!.env/bin/python

# Compute the success rates of different types of bills with
# different prognosis factors.

if __name__ == "__main__":
	import sys, os
	sys.path.insert(0, "..")
	sys.path.insert(0, ".")
	sys.path.insert(0, "lib")
	sys.path.insert(0, ".env/lib/python2.7/site-packages")
	os.environ["DJANGO_SETTINGS_MODULE"] = 'settings'

import lxml, scipy.stats, numpy, itertools, re, csv
from logistic_regression import *

from bill.models import *
from committee.models import *
from person.models import *
from person.types import RoleType
from person.analysis import load_sponsorship_analysis
from us import get_congress_dates

from django.db.models import Count

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
	# load archival committee data
	ROLE_MAPPING = { # from the committee parser
		'Ex Officio': CommitteeMemberRole.exofficio,
		'Chairman': CommitteeMemberRole.chairman,
		'Cochairman': CommitteeMemberRole.chairman, # huh!
		'Chair': CommitteeMemberRole.chairman,
		'Ranking Member': CommitteeMemberRole.ranking_member,
		'Vice Chairman': CommitteeMemberRole.vice_chairman,
		'Vice Chair': CommitteeMemberRole.vice_chairman,
		'Vice Chairwoman': CommitteeMemberRole.vice_chairman,
		'Member': CommitteeMemberRole.member,
	}
	committee_membership = { }
	for cnode in lxml.etree.parse("data/us/%d/committees.xml" % congress).xpath("committee|committee/subcommittee"):
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
	if (idate - get_congress_dates(bill.congress)[0].date()).days < 90:
		factors.append(("introduced_first90days", "The %s was introduced in the first 90 days of the Congress." % bill.noun, "Introduced in the first 90 days of the Congress (incl. companion bills)."))
	if (idate - get_congress_dates(bill.congress)[0].date()).days < 365:
		factors.append(("introduced_firstyear", "The %s was introduced in the first year of the Congress." % bill.noun, "Introduced in the first year of the Congress (incl. companion bills)."))
	if (get_congress_dates(bill.congress)[1].date() - idate).days < 90:
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
		for rname, rvalue in (("member", CommitteeMemberRole.member), ("rankingmember", CommitteeMemberRole.ranking_member), ("vicechair", CommitteeMemberRole.vice_chairman), ("chair", CommitteeMemberRole.chairman)):
			for committee in committees:
				if committee_membership.get(bill.sponsor_id, {}).get(committee.code) ==  rvalue:
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
	for rname, rvalue in (("committeemember", CommitteeMemberRole.member), ("rankingmember", CommitteeMemberRole.ranking_member), ("vicechair", CommitteeMemberRole.vice_chairman), ("chair", CommitteeMemberRole.chairman)):
		num_cosp = 0
		for cosponsor in cosponsors:
			for committee in committees:
				cvalue = committee_membership.get(cosponsor.person.id, {}).get(committee.code)
				if cvalue ==  rvalue or (rvalue==CommitteeMemberRole.member and cvalue != None):
					num_cosp += 1
					break
		if rvalue == CommitteeMemberRole.member:
			if num_cosp <= 2: # ranges are tweakable...
				num_cosp = str(num_cosp)
			if num_cosp <= 5:
				num_cosp = "3-5"
			else:
				num_cosp = "6+"
			factors.append( ("cosponsor_%s_%s" % (rname, num_cosp), "%s cosponsors serve on a committee to which the %s has been referred." % (num_cosp, bill.noun), "%s cosponsors are on a relevant committee." % num_cosp) )
		elif num_cosp > 0:
			rname2 = CommitteeMemberRole.by_value(rvalue).label.lower()
			factors.append( ("cosponsor_%s" % rname, "A cosponsor is the %s of a committee to which the %s has been referred." % (rname2, bill.noun), "A cosponsor is a relevant committee %s." % rname2))

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
				if reintro.current_status not in (BillStatus.introduced, BillStatus.referred):
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
					factors.append(("companion_bipartisan", "The %s's companion %s was sponsored by a member of the other party." % (bill.noun, rb.related_bill.display_number), "Has a companion bill sponsored by the other party."))
			
			for f in get_bill_factors(rb.related_bill, pop_title_prefixes, committee_membership, majority_party, lobbying_data, include_related_bills=False):
				if "startswith" in f[0]: continue # don't include title factors because the title is probs the same
				if f[0] in ("introduced_first90days", "introduced_last90days", "introduced_firstyear", "reintroduced_of_reported", "reintroduced"):
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

def build_model(congress):
	majority_party = load_majority_party(congress)
	committee_membership = load_committee_membership(congress)
	lobbying_data = None #load_lobbying_data(congress)
	
	# universe
	BILLS = Bill.objects.filter(congress=congress).prefetch_related()
	
	# compute the most frequent first few words of bills. slurp in all of the titles,
	# record the counts of all of the prefixes of the titles, and then take the top few,
	# excluding ones that are prefixes of another popular prefix.
	title_counts = { }
	for bill in BILLS:
		title = bill.title_no_number
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
		
	# We create separate models for bills by the bill type (H.R., S., H.Res., etc.)
	# and by whether the bill is introduced/referred or has been reported or more.
	# Once a bill has been reported by committee it's chances of success are
	# of course much higher, since the bills that have not been reported by committee
	# in historical data are necessarily failed bills. Also the models change
	# substantially.
		
	MODEL = dict()
	
	introduced_statuses = (BillStatus.introduced, BillStatus.referred)
	
	for (bill_type, bill_type_descr), is_introduced in itertools.product(BillType, (True, False)):
		#if bill_type != BillType.house_bill: continue
		#if bill_type not in (BillType.house_joint_resolution, BillType.senate_joint_resolution): continue
		
		bills = BILLS.filter(bill_type=bill_type)
		if not is_introduced:
			# When is_introduced is True, we scan across all bills, because all bills were
			# in the introduced/referred status at one point. If we filter it to bills whose
			# current status is introduced/referred, obviously they will all have been
			# failed bills, which defeats the purpose. When is_introduced is False, we
			# only look at bills that have at least gotten reported so that we can see
			# of reported bills which make it to success.
			bills = bills.exclude(current_status__in=introduced_statuses)

		print bill_type_descr, "introduced" if is_introduced else "reported"
		
		total = bills.count()
		
		if is_introduced:
			# for the introduced model, success is getting out of committee
			total_success = bills.exclude(current_status__in=introduced_statuses).count()
		else:
			# for the reported model, success is being enacted (or whatever final status as appropriate for the bill type)
			total_success = bills.filter(current_status__in=BillStatus.final_status_passed).count()
			
		print "\toverall", int(round(100.0*total_success/total)), "%; N=", total
		
		sorted_bills = { }
		regression_outcomes = [ ]
		regression_predictors = [ ]
		factor_descriptions = { }
		for bill in bills:
			#import random # speed this up?
			#if random.random() < .7: continue
			
			# What's the measured binary outcome for this bill? Check if the bill
			# ended in a success state.
			if is_introduced:
				success = bill.current_status not in introduced_statuses
			else:
				success = bill.current_status in BillStatus.final_status_passed
			
			# Get the binary factors that apply to this bill.
			factors = get_bill_factors(bill, pop_title_prefixes, committee_membership, majority_party, lobbying_data)
			
			# maintain a simple list of success percent rates for each factor individually
			for key, descr, general_descr in factors:
				if not key in sorted_bills: sorted_bills[key] = [0, 0] # count of total, successful
				sorted_bills[key][0] += 1
				if success: sorted_bills[key][1] += 1
				factor_descriptions[key] = general_descr
				
			# build data for a regression
			regression_outcomes.append(1.0 if success else 0.0)
			regression_predictors.append(set( f[0] for f in factors )) # extract just the key from the (key, descr) tuple
			
		# check which factors were useful
		significant_factors = dict()
		for key, bill_counts in sorted_bills.items():
			# create a binomial distribution based on the overall pass rate for this
			# type of bill (H.R., H.Res., etc.) and a draw the number of bills
			# within this subset (key) that are passed, and see if it is statistically
			# different from the overall count. only include statistical differences.
			if bill_counts[0] < 15: continue
			distr = scipy.stats.binom(bill_counts[0], float(total_success)/float(total))
			pless = distr.cdf(bill_counts[1])
			pmore = 1.0-distr.cdf(bill_counts[1])
			if pless < .015 or pmore < .015 or (total < 100 and (pless < .05 or pmore < .05)):
				# only show statistically significant differences from the group mean
				significant_factors[key] = (pless, pmore)
				
		# run a logistic regression
		regression_predictors_map = None
		regression_beta = None
		if len(significant_factors) > 0:
			regression_predictors_map = dict(reversed(e) for e in enumerate(significant_factors))
			regression_predictors_2 = [ [] for f in regression_predictors_map ]
			for factors in regression_predictors:
				for fname, findex in regression_predictors_map.items():
					regression_predictors_2[findex].append(1.0 if fname in factors else 0.0)
			regression_predictors_2 = numpy.array(regression_predictors_2)
			regression_outcomes = numpy.array(regression_outcomes)
			regression_beta, J_bar, l = logistic_regression(regression_predictors_2, regression_outcomes)
			
		# Generate the model for output.
		model = dict()
		MODEL[(bill_type,is_introduced)] = model
		if is_introduced:
			model["success_name"] = "sent out of committee to the floor"
		else:
			if bill_type in (BillType.senate_bill, BillType.house_bill):
				model["success_name"] = "enacted"
			elif bill_type in (BillType.senate_joint_resolution, BillType.house_joint_resolution):
				model["success_name"] = "enacted or passed"
			else:
				model["success_name"] = "agreed to"
		model["count"] = total
		model["success_rate"] = 100.0*total_success/total
		model["regression_predictors_map"] = regression_predictors_map
		model["regression_beta"] = list(regression_beta) if regression_beta != None else None
		model_factors = dict()
		model["factors"] = model_factors
		for key, bill_counts in sorted_bills.items():
			if key not in significant_factors: continue
			pless, pmore = significant_factors[key]
			print "\t" + key, int(round(100.0*bill_counts[1]/bill_counts[0])), "%; N=", bill_counts[0], "p<", int(round(100*pless)), int(round(100*pmore)), "B=", regression_beta[regression_predictors_map[key]+1]
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

def compute_prognosis_2(bill, committee_membership, majority_party, lobbying_data, proscore=False):
	import prognosis_model
	
	# get a list of (factorkey, descr) tuples of the factors that are true for
	# this bill. use the model to convert these tuples into %'s and descr's.
	factors = get_bill_factors(bill, prognosis_model.pop_title_prefixes, committee_membership, majority_party, lobbying_data)
	
	# There are two models for every bill, one from introduced to reported
	# and the other from reported to success.
	
	model_1 = prognosis_model.factors[(bill.bill_type, True)]
	model_2 = prognosis_model.factors[(bill.bill_type, False)]
	
	# Eliminate factors that are not used in either model.
	factors = [f for f in factors if f[0] in model_1["factors"] or f[0] in model_2["factors"]]
	
	# If we are doing a "proscore", remove any startswith factors that increase
	# a bill's prognosis. These are usually indicative of boring bills like renaming a
	# post office. Startswith factors that decrease a bill's prognosis are still good
	# to include.
	if proscore:
		factors = [(key, decr) for (key, decr) in factors if 
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
	
	is_introduced = bill.current_status in (BillStatus.introduced, BillStatus.referred)
	
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
		"prediction": (prediction_1 * prediction_2 / 100.0) if is_introduced else prediction_2,
		"success_name": model_2["success_name"],
		
		"factors_help_help": [descr for key, descr, gen_descr in factors if helps(key, True, True)],
		"factors_hurt_hurt": [descr for key, descr, gen_descr in factors if helps(key, False, False)],
		"factors_help_hurt": [descr for key, descr, gen_descr in factors if helps(key, True, False)],
		"factors_hurt_help": [descr for key, descr, gen_descr in factors if helps(key, False, True)],
	}

def compute_prognosis(bill, proscore=False):
	import prognosis_model
	majority_party = load_majority_party(bill.congress)
	committee_membership = load_committee_membership(bill.congress)
	prog = compute_prognosis_2(bill, committee_membership, majority_party, None, proscore=proscore)
	prog["congress"] = prognosis_model.congress
	return prog
		
def test_prognosis(congress):
	majority_party = load_majority_party(congress)
	committee_membership = load_committee_membership(congress)
	for bill in Bill.objects.filter(congress=congress, bill_type=BillType.house_bill):
		print bill
		print compute_prognosis_2(bill, committee_membership, majority_party)
		print
	
def top_prognosis(congress, bill_type):
	max_p = None
	max_b = None
	majority_party = load_majority_party(congress)
	committee_membership = load_committee_membership(congress)
	for bill in Bill.objects.filter(congress=congress, bill_type=bill_type):
		p = compute_prognosis_2(bill, committee_membership, majority_party)
		if not max_p or p["prediction"] > max_p:
			max_p = p["prediction"]
			max_b = bill
	print max_p, max_b
	
if __name__ == "__main__":
	build_model(111)
	#test_prognosis(112)
	#print compute_prognosis(Bill.objects.get(congress=112, bill_type=BillType.house_bill, number=1125))
	#print top_prognosis(112, BillType.house_bill)
	#print top_prognosis(112, BillType.senate_bill)
	


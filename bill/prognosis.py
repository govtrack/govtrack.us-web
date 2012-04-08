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

import lxml, scipy.stats, numpy, itertools
from logistic_regression import *

from bill.models import *
from committee.models import *
from person.models import *
from person.types import RoleType
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

def get_bill_factors(bill, pop_title_prefixes, committee_membership, majority_party):
	factors = list()
	
	# does the bill's title start with a common prefix?
	for prefix in pop_title_prefixes:
		if bill.title_no_number.startswith(prefix + " "):
			factors.append(("startswith:" + prefix, "The %s's title starts with \"%s.\"" % (bill.noun, prefix)))
	
	cosponsors = list(Cosponsor.objects.filter(bill=bill, withdrawn=None).select_related("person"))
	committees = list(bill.committees.all())
	
	maj_party = majority_party[bill.bill_type]
	
	if bill.sponsor:
		# party of the sponsor
		sponsor_party = bill.sponsor.get_role_at_date(bill.introduced_date).party
		if sponsor_party == maj_party:
			factors.append( ("sponsor_majority", "The sponsor is a member of the majority party.") )
		elif sponsor_party != "Independent": # ease of explanation
			factors.append( ("sponsor_minority", "The sponsor is a member of the minority party.") )
	
		# is the sponsor a member/chair of a committee to which the bill has
		# been referred?
		for rname, rvalue in (("member", CommitteeMemberRole.member), ("rankingmember", CommitteeMemberRole.ranking_member), ("vicechair", CommitteeMemberRole.vice_chairman), ("chair", CommitteeMemberRole.chairman)):
			for committee in committees:
				if committee_membership.get(bill.sponsor_id, {}).get(committee.code) ==  rvalue:
					if rvalue != CommitteeMemberRole.member:
						factors.append(("sponsor_committee_%s" % rname, "The sponsor is the %s of a committee to which the %s has been referred." % (CommitteeMemberRole.by_value(rvalue).label.lower(), bill.noun)))
					elif sponsor_party == maj_party:
						factors.append(("sponsor_committee_member_majority", "The sponsor is on a committee to which the %s has been referred, and the sponsor is a member of the majority party." % bill.noun))
					
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
			factors.append( ("cosponsor_%s_%s" % (rname, num_cosp), "%s cosponsors serve on a committee to which the %s has been referred." % (num_cosp, bill.noun)) )
		elif num_cosp > 0:
			factors.append( ("cosponsor_%s" % rname, "A cosponsor is the %s of a committee to which the %s has been referred." % (CommitteeMemberRole.by_value(rvalue).label.lower(), bill.noun)))

	# do we have cosponsors on both parties?
	num_cosp_majority = 0
	for cosponsor in cosponsors:
		if cosponsor.get_person_role().party == maj_party:
			num_cosp_majority += 1
	if bill.sponsor and sponsor_party == maj_party and len(cosponsors) >= 6 and num_cosp_majority < 2.0*len(cosponsors)/3:
		factors.append(("cosponsors_bipartisan", "While the sponsor is in the majority party, at least one third of the %s's cosponsors are from the minority party." % bill.noun))
	elif num_cosp_majority > 0 and num_cosp_majority < len(cosponsors):
		factors.append(("cosponsors_crosspartisan", "There is at least one cosponsor from the majority party and one cosponsor outside of the majority party."))
		
	return factors

def build_model(congress):
	majority_party = load_majority_party(congress)
	committee_membership = load_committee_membership(congress)
	
	# universe
	BILLS = Bill.objects.filter(congress=congress).select_related("sponsor")
	
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
		
	# We create separate models for bills by the bill type (H.R., S., H.Res., etc.)
	# and by whether the bill is introduced/referred or has been reported or more.
	# Once a bill has been reported by committee it's chances of success are
	# of course much higher, since the bills that have not been reported by committee
	# in historical data are necessarily failed bills.
		
	MODEL = dict()
	
	for (bill_type, bill_type_descr), is_introduced in itertools.product(BillType, (True, False)):
		bills = BILLS.filter(bill_type=bill_type)
		if not is_introduced:
			# When is_introduced is True, we scan across all bills, because all bills were
			# in the introduced/referred status at one point. If we filter it to bills whose
			# current status is introduced/referred, obviously they will all have been
			# failed bills, which defeats the purpose. When is_introduced is False, we
			# only look at bills that have at least gotten reported so that we can see
			# of reported bills which make it to success.
			bills = bills.exclude(current_status__in=(BillStatus.introduced, BillStatus.referred))

		print bill_type_descr, "introduced" if is_introduced else "reported"
		total = bills.count()
		passed = bills.filter(current_status__in=BillStatus.final_status_passed).count()
		print "\toverall", int(round(100.0*passed/total)), "%; N=", total
		
		sorted_bills = { }
		regression_outcomes = [ ]
		regression_predictors = [ ]
		for bill in bills:
			#import random # speed this up?
			#if random.random() < .7: continue
			
			success = bill.current_status in BillStatus.final_status_passed
			factors = get_bill_factors(bill, pop_title_prefixes, committee_membership, majority_party)
			
			# maintain a simple list of success percent rates for each factor individually
			for key, descr in factors:
				if not key in sorted_bills: sorted_bills[key] = [0, 0] # count of total, successful
				sorted_bills[key][0] += 1
				if success: sorted_bills[key][1] += 1
				
			# build data for a regression
			regression_outcomes.append(1.0 if success else 0.0)
			regression_predictors.append(factors)
			
		# check which factors were useful
		significant_factors = set()
		for key, bill_counts in sorted_bills.items():
			# create a binomial distribution based on the overall pass rate for this
			# type of bill (H.R., H.Res., etc.) and a draw the number of bills
			# within this subset (key) that are passed, and see if it is statistically
			# different from the overall count. only include statistical differences.
			if bill_counts[0] < 10: continue
			distr = scipy.stats.binom(bill_counts[0], float(passed)/float(total))
			pless = distr.cdf(bill_counts[1])
			pmore = 1.0-distr.cdf(bill_counts[1])
			if pless < .02 or pmore < .02:
				# only show statistically significant differences from the group mean
				significant_factors.add(key)
				
		# run a logistic regression
		regression_predictors_map = None
		regression_beta = None
		if len(significant_factors) > 0:
			regression_predictors_map = dict(reversed(e) for e in enumerate(significant_factors))
			regression_predictors_2 = [ [] for f in regression_predictors_map ]
			for factors in regression_predictors:
				factors2 = set(f[0] for f in factors) # factors is (name, descr) tuples, extract just the names
				for fname, findex in regression_predictors_map.items():
					regression_predictors_2[findex].append(1.0 if fname in factors2 else 0.0)
			regression_predictors_2 = numpy.array(regression_predictors_2)
			regression_outcomes = numpy.array(regression_outcomes)
			regression_beta, J_bar, l = logistic_regression(regression_predictors_2, regression_outcomes)
			
		# Generate the model for output.
		model = dict()
		MODEL[(bill_type,is_introduced)] = model
		if bill_type in (BillType.senate_bill, BillType.house_bill):
			model["success_name"] = "enacted"
		elif bill_type in (BillType.senate_joint_resolution, BillType.house_joint_resolution):
			model["success_name"] = "enacted or passed"
		else:
			model["success_name"] = "agreed to"
		model["count"] = total
		model["success_rate"] = 100.0*passed/total
		model["regression_predictors_map"] = regression_predictors_map
		model["regression_beta"] = list(regression_beta) if regression_beta != None else None
		model_factors = dict()
		model["factors"] = model_factors
		for key, bill_counts in sorted_bills.items():
			if key not in significant_factors: continue
			print "\t" + key, int(round(100.0*bill_counts[1]/bill_counts[0])), "%; N=", bill_counts[0], int(round(100*pless)), int(round(100*pmore))
			model_factors[key] = dict()
			model_factors[key]["count"] = bill_counts[0]
			model_factors[key]["success_rate"] = 100.0*bill_counts[1]/bill_counts[0]
			
	with open("prognosis_model.py", "w") as modelfile:
		modelfile.write("# this file was automatically generated by prognosis.py\n")
		modelfile.write("congress = %d\n" % congress)
		from pprint import pprint
		modelfile.write("pop_title_prefixes = ")
		pprint(pop_title_prefixes, modelfile)
		modelfile.write("factors = ")
		pprint(MODEL, modelfile)

def compute_prognosis_2(bill, committee_membership, majority_party):
	import prognosis_model
	
	# get a list of (factorkey, descr) tuples of the factors that are true for
	# this bill. use the model to convert these tuples into %'s and descr's.
	factors = get_bill_factors(bill, prognosis_model.pop_title_prefixes, committee_membership, majority_party)
	
	is_introduced = bill.current_status in (BillStatus.introduced, BillStatus.referred)
	
	model = prognosis_model.factors[(bill.bill_type, is_introduced)]
	
	factors_list = [{ "description": descr, "count": model["factors"][key]["count"], "success_rate": model["factors"][key]["success_rate"], "success_change": model["factors"][key]["success_rate"]-model["success_rate"] } for key, descr in factors if key in model["factors"]]
	factors_list.sort(key = lambda x : x["success_rate"], reverse=True)
	
	# if there is a factor that decreases the bill's chances of passing relative
	# to the overall mean, then reverse the order to highlight that.
	if len(factors_list) > 0 and factors_list[-1]["success_rate"] < model["success_rate"]:
		factors_list.reverse()
	
	# make a prediction using the logistic regression model
	if model["regression_beta"] == None:
		prediction = model["success_rate"]
	else:
		factor_keys = set(f[0] for f in factors)
		predictors = [0.0 for f in xrange(len(model["regression_beta"])-1)] # remove the intercept
		for key, index in model["regression_predictors_map"].items():
			predictors[index] = 1.0 if key in factor_keys else 0.0
		prediction = calcprob(model["regression_beta"], numpy.transpose(numpy.array([predictors])))
	
	return {
		"success_name": model["success_name"],
		"is_introduced": is_introduced,
		"overall_count": model["count"],
		"overall_success_rate": model["success_rate"],
		"prediction": float(prediction),
		"factors": factors_list,
	}

def compute_prognosis(bill):
	import prognosis_model
	majority_party = load_majority_party(bill.congress)
	committee_membership = load_committee_membership(bill.congress)
	prog = compute_prognosis_2(bill, committee_membership, majority_party)
	prog["congress"] = prognosis_model.congress
	return prog
		
def test_prognosis(congress):
	majority_party = load_majority_party(congress)
	committee_membership = load_committee_membership(congress)
	for bill in Bill.objects.filter(congress=congress, bill_type=BillType.house_bill):
		print bill
		print compute_prognosis_2(bill, committee_membership, majority_party)
		print
	
if __name__ == "__main__":
	build_model(111)
	#test_prognosis(112)

#!script

# Compute a year-end report for Members of Congress.
#
# Generate a bunch of statistics for each Member and then
# rank the results across subsets of Members to contextualize
# the information.

import sys, json, re

import us
import datetime # implicitly used in eval()'ing dates inside major_actions

from person.models import Person, PersonRole, RoleType
from bill.models import Cosponsor, Bill, BillStatus, RelatedBill, BillType
from vote.models import Vote, Voter, CongressChamber
from committee.models import CommitteeMemberRole

competitive_seats = None

def get_cohorts(person, role, congress, session, committee_membership):
	cohorts = []

	# chamber
	chamber = RoleType.by_value(role.role_type).congress_chamber.lower()
	cohorts.append({ "key": chamber })

	# party
	cohorts.append({ "key": "party-%s-%s" % (chamber, role.party.lower()), "chamber": chamber, "party": role.party })

	# state delegation
	if role.role_type == RoleType.representative:
		cohorts.append({ "key": "house-state-delegation-" + role.state.lower(), "state": role.state })

	# chamber leadership position
	if role.leadership_title:
		cohorts.append({ "key": chamber + "-leadership", "position": role.leadership_title })

	# freshmen/sophomores
	min_start_date = None
	prev_congresses_served = set()
	# use enddate__lte=endate to include the current role itself since for
	# senators their current role may span previous congresses
	for r in PersonRole.objects.filter(person=person, role_type=role.role_type, enddate__lte=role.enddate):
		if not min_start_date or r.startdate < min_start_date: min_start_date = r.startdate
		for c in r.congress_numbers():
			if c < congress:
				prev_congresses_served.add(c)
	if len(prev_congresses_served) == 0: cohorts.append({ "key": chamber + "-freshmen", "chamber": chamber })
	if len(prev_congresses_served) == 1: cohorts.append({ "key": chamber + "-sophomores", "chamber": chamber })
	if min_start_date and (role.enddate - min_start_date).days > 365.25*10: cohorts.append({ "key": chamber + "-tenyears", "chamber": chamber, "first_date": min_start_date.isoformat()  })

	# committee leadership positions
	committee_positions = []
	for committee, committee_role in committee_membership.get(person.id, {}).items():
		if len(committee) != 4: continue # exclude subcommittees
		if committee_role in (CommitteeMemberRole.ranking_member, CommitteeMemberRole.vice_chairman, CommitteeMemberRole.chairman):
			committee_positions.append( (committee, committee_role) )
	if len(committee_positions) > 0:
		cohorts.append({ "key": chamber + "-committee-leaders", "chamber": chamber, "positions": committee_positions })

	# safe vs competitive seats
	if role.role_type == RoleType.representative:
		global competitive_seats
		if competitive_seats is None:
			competitive_seats = set()
			for line in open("analysis/cook_competitive_seats-%s.txt" % session):
				if line[0] == "#": continue
				(state, district) = line.split(" ")[0].split("-")
				competitive_seats.add( (state, int(district)) )
		if (role.state, role.district) in competitive_seats:
			cohorts.append({ "key": chamber + "-competitive-seat" })
		else:
			cohorts.append({ "key": chamber + "-safe-seat" })

	return cohorts


def get_vote_stats(person, role, stats, votes_this_year):
	# Missed vote % in the chamber that the Member is currently serving in.
	if role.leadership_title == "Speaker": return
	votes_elligible = Voter.objects.filter(person=person, vote__in=votes_this_year[role.role_type])
	votes_missed = votes_elligible.filter(option__key="0")
	v1 = votes_elligible.count()
	v2 = votes_missed.count()
	stats["missed-votes"] = {
		"value": 100.0*float(v2)/float(v1) if v1 > 0 else None,
		"elligible": v1,
		"missed": v2,
		"role": RoleType.by_value(role.role_type).key,
	}

def was_bill_enacted(b, startdate, enddate, recurse=True):
	# Our status code is currently tied to the assignment of a slip
	# law number, which isn't what we mean exactly.
	#
	# (Additionally, we should count a bill as enacted if any identified companion
	# bill is enacted.)

	# TODO: See new function in the Bill model.

	# If it *was* assigned a slip law number, which in the future might
	# be useful for veto overrides, then OK.
	if b.current_status in BillStatus.final_status_passed_bill and \
		startdate <= b.current_status_date <= enddate:
		return True

	# Otherwise, check the actions for a <signed> action.
	fn = "data/congress/%s/bills/%s/%s%d/data.json" % (
    	b.congress,
        BillType.by_value(b.bill_type).slug,
        BillType.by_value(b.bill_type).slug,
        b.number)
	bj = json.load(open(fn))
	for axn in bj["actions"]:
		if axn["type"] == "signed" and startdate.isoformat() <= axn["acted_at"] <= enddate.isoformat():
			return True

	# Otherwise check companion bills.
	#if recurse:
	#	for rb in RelatedBill.objects.filter(bill=b, relation="identical").select_related("related_bill"):
	#		if was_bill_enacted(rb.related_bill, startdate, enddate, recurse=False):
	#			return True
			
	return False

def get_sponsor_stats(person, role, stats, congress, startdate, enddate, committee_membership):
	# How many bills did the Member introduce during this time window?
	bills = Bill.objects.filter(sponsor=person, congress=congress,
		introduced_date__gte=startdate, introduced_date__lte=enddate)
	stats["bills-introduced"] = {
		"value": bills.count(),
	}

	# How many bills were enacted within this time window?
	#bills_enacted = bills.filter(current_status__in=BillStatus.final_status_passed_bill,
	#	current_status_date__gte=startdate, current_status_date__lte=enddate)
	bills_enacted = [b for b in bills if was_bill_enacted(b, startdate, enddate)]
	stats["bills-enacted"] = {
		"value": len(bills_enacted),
		"bills": make_bill_entries(bills_enacted),
	}

	bills = list(bills)
	was_reported = []
	has_cmte_leaders = []
	has_cosponsors_both_parties = 0
	has_companion = []
	for bill in bills:
		# In order to test these remaining factors, we have to look more closely
		# at the bill because we can only use activities that ocurred during the
		# time window so that if we re-run this script on the same window at a
		# later date nothing changes -- i.e. future activitiy on bills should
		# not affect 1st Session statistics.

		# Check if the bill was reported during this time period.
		for datestr, st, text, srcxml in bill.major_actions:
			date = eval(datestr)
			if isinstance(date, datetime.datetime): date = date.date()
			if date >= startdate and date <= enddate and st == BillStatus.reported:
				was_reported.append(bill)
				break # make sure not to double-count any bills in case of data errors

		# Check whether any cosponsors are on relevant committees.
		cosponsors = list(Cosponsor.objects.filter(bill=bill, joined__gte=startdate, joined__lte=enddate).select_related("person", "role"))
		x = False
		for committee in list(bill.committees.all()):
			for cosponsor in cosponsors:
				if committee_membership.get(cosponsor.person.id, {}).get(committee.code) in (CommitteeMemberRole.ranking_member, CommitteeMemberRole.vice_chairman, CommitteeMemberRole.chairman):
					x = True
		if x: has_cmte_leaders.append(bill)

		# Check whether there's a cosponsor from both parties.
		co_d = False
		co_r = False
		for cosponsor in cosponsors:
			if cosponsor.role.party == "Democrat": co_d = True
			if cosponsor.role.party == "Republican": co_r = True
		if co_d and co_r:
			has_cosponsors_both_parties += 1

        # Check if a companion bill was introduced during the time period.
		if RelatedBill.objects.filter(bill=bill, relation="identical", related_bill__introduced_date__gte=startdate, related_bill__introduced_date__lte=enddate).exists():
			has_companion.append(bill)


	stats["bills-reported"] = {
		"value": len(was_reported),
		"bills": make_bill_entries(was_reported),
	}

	stats["bills-with-committee-leaders"] = {
		"value": len(has_cmte_leaders),
		"bills": make_bill_entries(has_cmte_leaders),
	}

	if len(bills) > 10:
		stats["bills-with-cosponsors-both-parties"] = {
			"value": 100.0*float(has_cosponsors_both_parties)/float(len(bills)),
			"num_bills": len(bills),
		}

	stats["bills-with-companion"] = {
		"value": len(has_companion),
		"other_chamber": RoleType.by_value(role.role_type).congress_chamber_other,
		"bills": make_bill_entries(has_companion),
	}

def get_cosponsor_stats(person, role, stats, congress, startdate, enddate):
	# Count of cosponsors on the Member's bills with a join date in this session.
	cosponsors = Cosponsor.objects.filter(bill__sponsor=person, bill__congress=congress, joined__gte=startdate, joined__lte=enddate)
	stats["cosponsors"] = {
		"value": cosponsors.count(),
	}

def get_cosponsored_stats(person, role, stats, congress, startdate, enddate):
	# Count of bills this person cosponsored.
	cosponsored = Cosponsor.objects.filter(person=person, bill__congress=congress, joined__gte=startdate, joined__lte=enddate)
	stats["cosponsored"] = {
		"value": cosponsored.count(),
	}

	# Of those bills, how many sponsored by a member of the other party.
	if role.party in ("Democrat", "Republican") and cosponsored.count() > 10:
		cosponsored_bi = cosponsored.exclude(bill__sponsor_role__party=role.party)
		stats["cosponsored-other-party"] = {
			"value": 100.0 * float(cosponsored_bi.count()) / float(cosponsored.count()),
			"cosponsored": cosponsored.count(),
			"cosponsored_other_party": cosponsored_bi.count(),
		}


def run_sponsorship_analysis(people, congress, startdate, enddate):
	# Run our own ideology and leadership analysis. While the chart we show on
	# people pages looks over the last several years of activity, for the year-end
	# stats we just want to look at activity during this year. This puts freshmen
	# Members on a more equal footing.
	global sponsorship_analysis_data
	from analysis.sponsorship_analysis import *
	sponsorship_analysis_data = { }
	peoplemap, people_list = get_people([role for (person,role) in people])
	for chamber, role_type in (('h', RoleType.representative), ('s', RoleType.senator)):
		bills_start_date, bills_end_date, rep_to_row, nreps, P = build_matrix(
			congress, congress, chamber, peoplemap, people_list,
			filter_startdate=startdate.isoformat(), filter_enddate=enddate.isoformat())
		smooth_matrix(nreps, P)
		parties = build_party_list(rep_to_row, peoplemap, nreps)
		spectrum = ideology_analysis(nreps, parties, P)
		pagerank = leadership_analysis(nreps, P)
		for id, index in rep_to_row.items():
			sponsorship_analysis_data[ (role_type, id) ] = (spectrum[index], pagerank[index])

def get_sponsorship_analysis_stats(person, role, stats):
	global sponsorship_analysis_data
	s = sponsorship_analysis_data.get( (role.role_type, person.id) )
	stats["ideology"] = {
		"value": s[0] if s else None,
		"role": RoleType.by_value(role.role_type).key,
	}
	stats["leadership"] = {
		"value": s[1] if s else None,
		"role": RoleType.by_value(role.role_type).key,
	}

def get_committee_stats(person, role, stats, committee_membership):
	chair_list = [] # chair, vicechair, or ranking member
	subchair_list = []
	for committee, role_type in committee_membership.get(person.id, {}).items():
		if role_type not in (CommitteeMemberRole.ranking_member, CommitteeMemberRole.vice_chairman, CommitteeMemberRole.chairman):
			continue
		if len(committee) == 4:
			# full committee
			chair_list.append( (committee, role_type) )
		else:
			subchair_list.append( (committee, role_type) )

	stats["committee-positions"] = {
		"value": 5*len(chair_list) + len(subchair_list),
		"committees": chair_list,
		"subcommittees": subchair_list,
	}

transparency_bills = None
def get_transparency_stats(person, role, stats, congress, startdate, enddate):
	global transparency_bills
	if not transparency_bills:
		transparency_bills = []
		for line in open("analysis/transparency-bills.txt"):
			bill = Bill.from_congressproject_id(re.split("\s", line)[0])
			transparency_bills.append(bill)

	# which bills are in the right chamber?
	plausible_bills = []
	for bill in transparency_bills:
		if BillType.by_value(bill.bill_type).chamber == RoleType.by_value(role.role_type).congress_chamber:
			plausible_bills.append(bill)

	# did person sponsor any of these within this session?
	sponsored = []
	for bill in transparency_bills:
		if startdate <= bill.introduced_date <= enddate and bill.sponsor == person:
			sponsored.append(bill)

	# did person cosponsor any of these within this session?
	cosponsored = []
	for cosp in Cosponsor.objects.filter(person=person, bill__in=transparency_bills, joined__gte=startdate, joined__lte=enddate):
		cosponsored.append(cosp.bill)

	stats["transparency-bills"] = {
		"value": len(sponsored)*3 + len(cosponsored),
		"sponsored": make_bill_entries(sponsored),
		"cosponsored": make_bill_entries(cosponsored),
		"num_bills": len(plausible_bills),
		"chamber": RoleType.by_value(role.role_type).congress_chamber,
	}

def make_bill_entries(bills):
	return [make_bill_entry(b) for b in bills]
def make_bill_entry(bill):
	return (unicode(bill), bill.get_absolute_url())

def collect_stats(session):
	# Get the congress and start/end dates of the session that this corresponds to.
	for congress, s, startdate, enddate in us.get_all_sessions():
		if s == session:
			break
	else:
		raise ValueError("Invalid session: " + session)

	# Who was serving on the last day of the session?
	people = [(r.person, r) for r in PersonRole.objects
		.filter(
			role_type__in=(RoleType.representative, RoleType.senator),
			startdate__lt=enddate, # use __lt and not __lte in case of multiple roles on the same day
			enddate__gte=enddate, # use __lte in case anyone's term ended exactly on this day
			)
		.select_related("person")]

	# Do a sponsorship analysis for bills in this session only.
	run_sponsorship_analysis(people, congress, startdate, enddate)

	# Get the committee members.
	from bill.prognosis import load_committee_membership
	committee_membership = load_committee_membership(congress)

	# Pre-fetch all of the votes in this session.
	votes_this_year = Vote.objects.filter(congress=congress, session=session)
	votes_this_year = {
		RoleType.representative: set(votes_this_year.filter(chamber=CongressChamber.house).values_list("id", flat=True)),
		RoleType.senator: set(votes_this_year.filter(chamber=CongressChamber.senate).values_list("id", flat=True)),
	}


	# Generate raw statistics.
	AllStats = { }
	for person, role in people:
		AllStats[person.id] = {
			"id": person.id,

			"role_id": role.id,
			"role_type": role.role_type,
			"role_start": role.startdate.isoformat(),
			"role_end": role.enddate.isoformat(),

			"stats": { },
			"cohorts": get_cohorts(person, role, congress, session, committee_membership),
		}

		stats = AllStats[person.id]["stats"]
		get_vote_stats(person, role, stats, votes_this_year)
		get_sponsor_stats(person, role, stats, congress, startdate, enddate, committee_membership)
		get_cosponsor_stats(person, role, stats, congress, startdate, enddate)
		get_cosponsored_stats(person, role, stats, congress, startdate, enddate)
		get_sponsorship_analysis_stats(person, role, stats)
		get_committee_stats(person, role, stats, committee_membership)
		get_transparency_stats(person, role, stats, congress, startdate, enddate)

	return AllStats

def contextualize(stats):
	# For each statistic compute ranks and percentiles within
	# each cohort.

	# collect all of the data
	population = { }
	for id, moc in stats.items():
		## TODO: remove
		#from bill.prognosis import load_committee_membership
		#committee_membership = load_committee_membership(113)
		#moc["cohorts"] = get_cohorts(Person.objects.get(id=id), PersonRole.objects.get(person__id=id, current=True), 113, committee_membership)

		# what cohots is the member a member of?
		for cohort in moc["cohorts"]:
			for stat in moc["stats"]:
				value = moc["stats"][stat].get("value")
				if value is not None:
					population.setdefault( (cohort["key"], stat), [] ).append(value)

	# now go back over it and for each statistic gathered paste
	# in the context by cohort
	for moc in stats.values():
		for statname, statinfo in moc["stats"].items():
			value = statinfo.get("value")
			if value is None: continue
			statinfo["context"] = { }
			for cohort in moc["cohorts"]:
				pop = population[(cohort["key"], statname)]

				# don't bother with context for very small cohorts
				if len(pop) < 6: continue

				context = statinfo["context"].setdefault(cohort["key"], { })

				# count individuals in the cohort population with a lower value
				num_ties = sum(1 if v == value else 0 for v in pop) - 1 # minus himself
				context["rank_ascending"] = sum(1 if v < value else 0 for v in pop) + 1
				context["rank_descending"] = sum(1 if v > value else 0 for v in pop) + 1
				context["rank_ties"] = num_ties
				context["percentile"] = int(round(100 * sum(1 if v < value else 0 for v in pop) / float(len(pop))))
				context["N"] = len(pop)
				context["min"] = min(pop)
				context["max"] = max(pop)



if __name__ == "__main__":
	# What session?
	session = sys.argv[1]
	stats = collect_stats(session)
	#stats = json.load(open(sys.argv[1]))['people']
	contextualize(stats)
	stats = {
		"meta": {
			"as-of": datetime.datetime.now().isoformat(),
		},
		"people": stats,
	}
	json.dump(stats, sys.stdout, indent=2, sort_keys=True)


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
	years_served = 0
	prev_congresses_served = set()
	# use enddate__lte=endate to include the current role itself since for
	# senators their current role may span previous congresses
	for r in PersonRole.objects.filter(person=person, role_type=role.role_type, enddate__lte=role.enddate):
		if not min_start_date or r.startdate < min_start_date: min_start_date = r.startdate
		years_served += round( (min(r.enddate,datetime.datetime.now().date())-r.startdate).days / 365.25 ) # end dates for senators may be far in the future; round because terms may be slightly less than a year
		for c in r.congress_numbers():
			if c < congress:
				prev_congresses_served.add(c)
	if person.id in (412505, 412503, 412506, 412507):
		# Schatz served only a few days in the 112th Congress. Other members took office
		# within the last two months of the 112th Congress. For the 2013 stats, I originally
		# classified them as sophomores. I revised it to drop that cohort from Schatz after
		# hearing from his office. For 2014 stats, I am classifying them all as a freshman
		# rather than sophomores; for 2015/2016 I am classifying them as sophomores.
		if session == "2014":
			assert prev_congresses_served == { 112 }
			prev_congresses_served = set()
		elif session in ("2015", "2016"):
			assert prev_congresses_served == { 112, 113 }
			prev_congresses_served = set([113])
	if person.id in (412605, 412606, 412607):
		# Similarly, Dave Brat (412605), Donald Norcross (412606), and Alma Adams (412607)
		# took office on 2014-11-12, but we'll treat them as freshman in the 114th Congress
		# rather than sophomores.
		if session in ("2015", "2016"):
			assert prev_congresses_served == { 113 }
			prev_congresses_served = set()
		elif session in ("2017", "2018"):
			assert prev_congresses_served == { 113, 114 }
			prev_congresses_served = set([114])
	if person.id in (412676, 412676):
		# Similarly, James Comer, Dwight Evans took office only after the 2016 election, so we'll
		# keep them as a freshman again in 2017, 2018 and then sophomores in 2019, 2020.
		if session in ("2017", "2018"):
			assert prev_congresses_served == { 114 }
			prev_congresses_served = set()
		elif session in ("2019", "2020"):
			assert prev_congresses_served == { 114, 115 }
			prev_congresses_served = set([115])
	if len(prev_congresses_served) == 0: cohorts.append({ "key": chamber + "-freshmen", "chamber": chamber })
	if len(prev_congresses_served) == 1: cohorts.append({ "key": chamber + "-sophomores", "chamber": chamber })
	if years_served >= 10: cohorts.append({ "key": chamber + "-tenyears", "chamber": chamber, "first_date": min_start_date.isoformat()  })

	return cohorts


def get_vote_stats(person, role, stats, votes_this_year):
	# Missed vote % in the chamber that the Member is currently serving in.
	if role.leadership_title == "Speaker": return
	votes_elligible = Voter.objects.filter(person=person, vote__in=votes_this_year[role.role_type])
	votes_missed = votes_elligible.filter(option__key="0")
	v1 = votes_elligible.count()
	v2 = votes_missed.count()
	stats["missed-votes"] = {
		"value": round(100.0*v2/v1, 3) if v1 > 0 else None,
		"elligible": v1,
		"missed": v2,
		"role": RoleType.by_value(role.role_type).key,
	}


def get_sponsor_stats(person, role, stats, congress, startdate, enddate, committee_membership):
	# How many bills did the Member introduce during this time window?
	bills = Bill.objects.filter(sponsor=person, congress=congress,
		introduced_date__gte=startdate, introduced_date__lte=enddate)
	stats["bills-introduced"] = {
		"value": bills.count(),
	}

	# How many bills were "enacted" within this time window? Follow the was_enacted_ex logic
	# which includes text incorporation. Only use the date range on single-year stats because
	# a bill might be enacted after the end of a Congress.
	def was_bill_enacted(b, startdate, enddate):
		if (enddate-startdate).days > 365*1.5:
			return b.was_enacted_ex()
		else:
			return b.was_enacted_ex(restrict_to_activity_in_date_range=(startdate, enddate))
	bills_enacted = [b for b in bills if was_bill_enacted(b, startdate, enddate)]
	stats["bills-enacted-ti"] = {
		"value": len(bills_enacted),
		"bills": make_bill_entries(bills_enacted),
	}

	# In order to test these remaining factors, we have to look more closely
	# at the bill because we can only use activities that ocurred during the
	# time window so that if we re-run this script on the same window at a
	# later date nothing changes -- i.e. future activitiy on bills should
	# not affect 1st Session statistics. Mostly.
	bills = list(bills)
	was_reported = []
	has_cmte_leaders = []
	has_cosponsors_both_parties = []
	has_companion = []
	for bill in bills:
		# Check if the bill was reported during this time period.
		for datestr, st, text, srcxml in bill.major_actions:
			date = eval(datestr)
			if isinstance(date, datetime.datetime): date = date.date()
			if date >= startdate and date <= enddate and st == BillStatus.reported:
				was_reported.append(bill)
				break # make sure not to double-count any bills in case of data errors

		# Check whether any cosponsors are on relevant committees.
		# Warning: Committee membership data is volatile, so re-running the stats may come out different.
		cosponsors = list(Cosponsor.objects.filter(bill=bill, joined__gte=startdate, joined__lte=enddate).select_related("person", "role"))
		x = False
		for committee in list(bill.committees.all()):
			for cosponsor in cosponsors:
				if committee_membership.get(cosponsor.person.id, {}).get(committee.code) in (CommitteeMemberRole.ranking_member, CommitteeMemberRole.vice_chair, CommitteeMemberRole.chair):
					x = True
		if x: has_cmte_leaders.append(bill)

		# Check whether there's a cosponsor from both parties.
		# Warning: If someone switches parties, this will change.
		co_d = False
		co_r = False
		for cosponsor in cosponsors:
			if cosponsor.role.party == "Democrat": co_d = True
			if cosponsor.role.party == "Republican": co_r = True
		if co_d and co_r:
			has_cosponsors_both_parties.append(bill)

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

	stats["bills-with-cosponsors-both-parties-count"] = {
		"value": len(has_cosponsors_both_parties),
		"bills": make_bill_entries(has_cosponsors_both_parties),
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
		if role_type not in (CommitteeMemberRole.ranking_member, CommitteeMemberRole.vice_chair, CommitteeMemberRole.chair):
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
			if bill.congress != congress: continue
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
	return ((bill.display_number_no_congress_number + ": " +  bill.title_no_number), bill.get_absolute_url())

def collect_stats(session):
	# Get the congress and start/end dates of the session that this corresponds to.
	if int(session) < 1000:
		# Specifies a Congress.
		congress = int(session)
		session = None
		is_full_congress_stats = True

		# Get the last session in the Congress.
		for c, s, x, y in us.get_all_sessions():
			if c == congress:
				session2 = s
				last_day_of_session = y

		# Dummy dates. Don't want to use the congress dates because a bill can be
		# enacted after the end of the Congress.
		startdate = datetime.date.min
		enddate = datetime.date.max
	else:
		is_full_congress_stats = False
		session2 = session
		for congress, s, startdate, enddate in us.get_all_sessions():
			if s == session:
				break
		else:
			raise ValueError("Invalid session: " + session)
		last_day_of_session = enddate

	# Who was serving on the last day of the session?
	people = [(r.person, r) for r in PersonRole.objects
		.filter(
			role_type__in=(RoleType.representative, RoleType.senator),
			startdate__lt=last_day_of_session, # use __lt and not __lte in case of multiple roles on the same day
			enddate__gte=last_day_of_session, # use __lte in case anyone's term ended exactly on this day
			)
		.select_related("person")]

	# Do a sponsorship analysis for bills in this session only.
	run_sponsorship_analysis(people, congress, startdate, enddate)

	# Get the committee members.
	from bill.prognosis import load_committee_membership
	committee_membership = load_committee_membership(congress)

	# Pre-fetch all of the votes in this session.
	votes_this_year = Vote.objects.filter(congress=congress)
	if session:
		votes_this_year = votes_this_year.filter(session=session)
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
			"cohorts": get_cohorts(person, role, congress, session2, committee_membership),
		}

		stats = AllStats[person.id]["stats"]
		get_vote_stats(person, role, stats, votes_this_year)
		get_sponsor_stats(person, role, stats, congress, startdate, enddate, committee_membership)
		get_cosponsor_stats(person, role, stats, congress, startdate, enddate)
		get_cosponsored_stats(person, role, stats, congress, startdate, enddate)
		get_sponsorship_analysis_stats(person, role, stats)
		get_committee_stats(person, role, stats, committee_membership)
		get_transparency_stats(person, role, stats, congress, startdate, enddate)

	return AllStats, congress, is_full_congress_stats

def contextualize(stats):
	# For each statistic compute ranks and percentiles within
	# each cohort.

	# collect all of the data
	population = { }
	for id, moc in stats.items():
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
	# What Congress (113, 114, 115...) or session (2015, 2017, ...)?
	congress_or_session = sys.argv[1]
	try:
		notes = sys.argv[2]
	except:
		notes = ""
	stats, congress, is_full_congress_stats = collect_stats(congress_or_session)
	#stats = json.load(open(sys.argv[1]))['people']
	contextualize(stats)
	stats = {
		"meta": {
			"as-of": datetime.datetime.now().isoformat(),
			"notes": notes,
			"congress": congress,
			"session": "2016",
			"is_full_congress_stats": is_full_congress_stats,
		},
		"people": stats,
	}
	json.dump(stats, sys.stdout, indent=2, sort_keys=True)


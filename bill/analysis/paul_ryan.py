#!script

from datetime import datetime, date
from numpy import mean, median, percentile
from scipy.stats import percentileofscore

from person.models import Person, PersonRole
from bill.models import Bill, Cosponsor, BillType
from bill.status import BillStatus
from committee.models import CommitteeMember, CommitteeMemberRole
from vote.models import VoteCategory, VoteOption

paul_ryan = Person.objects.get(id=400351)
paul_ryan_role = paul_ryan.roles_condensed()[0]

joe_biden = Person.objects.get(id=300008)
barak_obama = Person.objects.get(id=400629)

#for b1 in (Bill.objects.filter(cosponsors=paul_ryan) | Bill.objects.filter(sponsor=paul_ryan)).distinct():
#	for b2 in b1.get_related_bills():
#		if b2.relation == "identical":
#			if b2.related_bill.sponsor == joe_biden or b2.related_bill.sponsor == barak_obama:
#				# or joe_biden in b2.related_bill.cosponsors.all() or barak_obama in b2.related_bill.cosponsors.all():
#				print b1
#				print b2.related_bill
#				print b1.sponsor, b2.related_bill.sponsor
#				print
#
#results = []
#tot = 0
#for b in Bill.objects.filter(votes__voters__person=paul_ryan, votes__category__in=(VoteCategory.passage, VoteCategory.passage_suspension, VoteCategory.veto_override)).filter(votes__voters__person=joe_biden, votes__category__in=(VoteCategory.passage, VoteCategory.passage_suspension, VoteCategory.veto_override)).distinct():
#	votes = { paul_ryan: set(), joe_biden: set() }
#	for v in b.votes.filter(category__in=(VoteCategory.passage, VoteCategory.passage_suspension, VoteCategory.veto_override)):
#		if v.total_plus == 0 or v.total_minus == 0: continue
#		for vv in v.voters.filter(person__in=(paul_ryan, joe_biden)):
#				votes[vv.person].add(vv.option.key)
#	if len(votes[paul_ryan] & votes[joe_biden]) == 1:
#		results.append( (b, "".join(votes[paul_ryan] & votes[joe_biden])) )
#	tot += 1
#results.sort(key = lambda b : (
#		"Appropriation" in b[0].title or "Authorization" in b[0].title,
#		b[0].current_status != 28,
#		-b[0].proscore() ))
#import csv
#wr = csv.writer(open("veep_common_bills.csv", "w"))
#wr.writerow(("Vote", "Bill Status", "Bill Title", "Link"))
#for r in results:
#	wr.writerow((r[1].replace("+", "Support").replace("-", "Oppose"), r[0].get_current_status_display().replace("Signed by the President", "Enacted"), r[0].title.encode("utf8"), "http://www.govtrack.us" + r[0].get_absolute_url()))
#
#print len(results), tot

#import sys
#sys.exit()

all_congressmen =set([p for p in Person.objects\
	.filter(roles__enddate__gt=datetime.now(), roles__role_type=paul_ryan_role.role_type).distinct()\
	]) 

republican_congresspeeps_serving_as_long = set([p for p in Person.objects\
	.filter(roles__enddate__gt=datetime.now(), roles__role_type=paul_ryan_role.role_type, roles__party=paul_ryan_role.party).distinct()\
	if p.roles_condensed()[0].startdate <= paul_ryan_role.startdate])

republican_congresspeeps = set([p for p in Person.objects\
	.filter(roles__enddate__gt=datetime.now(), roles__role_type=paul_ryan_role.role_type, roles__party=paul_ryan_role.party).distinct()])

republican_new_congresspeeps = set([p for p in Person.objects\
	.filter(roles__enddate__gt=datetime.now(), roles__role_type=paul_ryan_role.role_type, roles__party=paul_ryan_role.party).distinct() if p.roles_condensed()[0].startdate == date(2011, 1, 5)])

republican_non_new_congresspeeps = set([p for p in Person.objects\
	.filter(roles__enddate__gt=datetime.now(), roles__role_type=paul_ryan_role.role_type, roles__party=paul_ryan_role.party).distinct() if p.roles_condensed()[0].startdate < date(2011, 1, 1)])

democratic_congresspeeps = set([p for p in Person.objects\
	.filter(roles__enddate__gt=datetime.now(), roles__role_type=paul_ryan_role.role_type).exclude(roles__party=paul_ryan_role.party).distinct()])

def is_chair(person):
	return 1 if CommitteeMember.objects.filter(person=person, role=CommitteeMemberRole.chair, committee__committee=None).exists() else 0

def pct_dem_cosponsors(person):
	c = Cosponsor.objects.filter(bill__sponsor=person)
	return float(c.filter(role__party="Democrat").count())/float(c.count())

def pct_dem_bills(person):
	c = Cosponsor.objects.filter(person=person)
	return float(c.filter(bill__sponsor_role__party="Democrat").count())/float(c.count())

def leadership_score(person):
	from person.analysis import load_sponsorship_analysis
	v = load_sponsorship_analysis(person)["leadership"]
	if v == None: return None
	return float(v)
	
def bills_enacted(person):
	return Bill.objects.filter(sponsor=person, bill_type=BillType.house_bill, current_status__in=BillStatus.final_status_enacted_bill).count()

def make_stat(descr, pop, stat):
	vals = [stat(p) for p in pop]
	vals = [v for v in vals if v != None]
	v = stat(paul_ryan)
	print(descr)
	print("value", round(v, 2), "N=", len(vals), "mean", round(mean(vals), 2), "median", round(median(vals), 2), "percentile", round(percentileofscore(vals, v)))
	print()

make_stat("#enacted; congressmen", all_congressmen, bills_enacted)
make_stat("#enacted; republicans tenure as long", republican_congresspeeps_serving_as_long, bills_enacted)

make_stat("leadership; republican", republican_congresspeeps, leadership_score)
make_stat("leadership; republican tenure as long", republican_congresspeeps_serving_as_long, leadership_score)
make_stat("leadership; republican non-freshmen", republican_non_new_congresspeeps, leadership_score)
make_stat("leadership; republican freshmen", republican_new_congresspeeps, leadership_score)


make_stat("chair; republican", republican_congresspeeps, is_chair)
make_stat("chair; republican tenure as long", republican_congresspeeps_serving_as_long, is_chair)

print("Ryan cosponsored", Cosponsor.objects.filter(person=paul_ryan).count())
make_stat("% dem bills; republican", republican_congresspeeps, pct_dem_bills)
make_stat("% dem bills; republican tenure as long", republican_congresspeeps_serving_as_long, pct_dem_bills)
make_stat("% dem bills; republican non-freshmen", republican_non_new_congresspeeps, pct_dem_bills)
make_stat("% dem bills; republican freshmen", republican_new_congresspeeps, pct_dem_bills)

print("Ryan sponsored", Bill.objects.filter(sponsor=paul_ryan).count())
make_stat("% cosponsors dem; republican", republican_congresspeeps, pct_dem_cosponsors)
make_stat("% cosponsors dem; republican tenure as long", republican_congresspeeps_serving_as_long, pct_dem_cosponsors)
make_stat("% cosponsors dem; republican non-freshmen", republican_non_new_congresspeeps, pct_dem_cosponsors)
make_stat("% cosponsors dem; republican freshmen", republican_new_congresspeeps, pct_dem_cosponsors)


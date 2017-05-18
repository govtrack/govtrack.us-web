#!script

from datetime import datetime, date
from numpy import mean, median, percentile
from scipy.stats import percentileofscore

from person.models import Person, PersonRole
from bill.models import Bill, Cosponsor, BillType
from bill.status import BillStatus
from committee.models import CommitteeMember, CommitteeMemberRole
from vote.models import VoteCategory, VoteOption

todd_akin = Person.objects.get(id=400005)
todd_akin_role = todd_akin.roles_condensed()[0]

all_congressmen =set([p for p in Person.objects\
	.filter(roles__enddate__gt=datetime.now(), roles__role_type=todd_akin_role.role_type).distinct()\
	]) 

republican_congresspeeps_serving_as_long = set([p for p in Person.objects\
	.filter(roles__enddate__gt=datetime.now(), roles__role_type=todd_akin_role.role_type, roles__party=todd_akin_role.party).distinct()\
	if p.roles_condensed()[0].startdate <= todd_akin_role.startdate])

republican_congresspeeps = set([p for p in Person.objects\
	.filter(roles__enddate__gt=datetime.now(), roles__role_type=todd_akin_role.role_type, roles__party=todd_akin_role.party).distinct()])

republican_new_congresspeeps = set([p for p in Person.objects\
	.filter(roles__enddate__gt=datetime.now(), roles__role_type=todd_akin_role.role_type, roles__party=todd_akin_role.party).distinct() if p.roles_condensed()[0].startdate == date(2011, 1, 5)])

republican_non_new_congresspeeps = set([p for p in Person.objects\
	.filter(roles__enddate__gt=datetime.now(), roles__role_type=todd_akin_role.role_type, roles__party=todd_akin_role.party).distinct() if p.roles_condensed()[0].startdate < date(2011, 1, 1)])

democratic_congresspeeps = set([p for p in Person.objects\
	.filter(roles__enddate__gt=datetime.now(), roles__role_type=todd_akin_role.role_type).exclude(roles__party=todd_akin_role.party).distinct()])

def is_chair(person):
	return 1 if CommitteeMember.objects.filter(person=person, role=CommitteeMemberRole.chairman, committee__committee=None).exists() else 0

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
	v = stat(todd_akin)
	print descr
	print "value", round(v, 2), "N=", len(vals), "mean", round(mean(vals), 2), "median", round(median(vals), 2), "percentile", round(percentileofscore(vals, v))
	print

make_stat("#enacted; congressmen", all_congressmen, bills_enacted)
make_stat("#enacted; republicans tenure as long", republican_congresspeeps_serving_as_long, bills_enacted)

make_stat("leadership; republican", republican_congresspeeps, leadership_score)
make_stat("leadership; republican tenure as long", republican_congresspeeps_serving_as_long, leadership_score)
make_stat("leadership; republican non-freshmen", republican_non_new_congresspeeps, leadership_score)
make_stat("leadership; republican freshmen", republican_new_congresspeeps, leadership_score)


make_stat("chair; republican", republican_congresspeeps, is_chair)
make_stat("chair; republican tenure as long", republican_congresspeeps_serving_as_long, is_chair)

print "cosponsored", Cosponsor.objects.filter(person=todd_akin).count()
make_stat("% dem bills; republican", republican_congresspeeps, pct_dem_bills)
make_stat("% dem bills; republican tenure as long", republican_congresspeeps_serving_as_long, pct_dem_bills)
make_stat("% dem bills; republican non-freshmen", republican_non_new_congresspeeps, pct_dem_bills)
make_stat("% dem bills; republican freshmen", republican_new_congresspeeps, pct_dem_bills)

print "sponsored", Bill.objects.filter(sponsor=todd_akin).count()
make_stat("% cosponsors dem; republican", republican_congresspeeps, pct_dem_cosponsors)
make_stat("% cosponsors dem; republican tenure as long", republican_congresspeeps_serving_as_long, pct_dem_cosponsors)
make_stat("% cosponsors dem; republican non-freshmen", republican_non_new_congresspeeps, pct_dem_cosponsors)
make_stat("% cosponsors dem; republican freshmen", republican_new_congresspeeps, pct_dem_cosponsors)


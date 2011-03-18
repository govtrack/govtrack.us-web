from person.models import Person
from committee.models import Committee
from events import models

class Feed(object):
    @staticmethod
    def from_name(name):
        if name in NoArgFeed.feedmap:
            return NoArgFeed.feedmap[name]
        
        args = name.split(":")
        if args[0] in OneArgFeed.feedmap:
            clz = OneArgFeed.feedmap[args[0]]
            return clz(":".join(args[1:]))
            
        return None
        
    def expand(self):
        return [self]
        
    @staticmethod
    def get_events_for(feeds):
        fd = []
        for f in feeds:
           fd.extend(f.expand()) 
        return models.Event.objects.filter(feed__feedclass__in=fd).order_by("-when")
        
    def get_events(self):
        return Feed.get_events_for((self,))

class NoArgFeed(Feed):
    feedmap = { }
    
    name = None
    
    def __unicode__(self):
        return self.name
    def _getstate__(self):
        return False  # prevent serialization of other information stored with the class
    
class OneArgFeed(Feed):
    feedmap = { }
    
    prefix = None
    arg = None
    
    def __init__(self, arg):
        self.arg = arg
    
    def name(self):
        return self.prefix + ":" + str(self.arg)

    def __unicode__(self):
        return self.name()
    def _getstate__(self):
        return { "arg": arg } # prevent serialization of other information

class PersonFeed(OneArgFeed):
    prefix = "p"
    _person = None
    
    def person(self):
        if self._person == None:
            self._person = Person.objects.get(id=int(self.arg))
        return self._person
        
    def display(self):
        return self.person().name()
        
    def expand(self):
        if self.__class__ == PersonFeed:
            return [PersonVotesFeed(self.arg), PersonSponsorshipFeed(self.arg)]
        else:
            return [self]

class PersonVotesFeed(PersonFeed):
    prefix = "pv"
    localname = "Voting Record"

    def display(self):
        return self.person().name() + "'s Voting Record"

class PersonSponsorshipFeed(PersonFeed):
    prefix = "ps"
    localname = "Bills Sponsored"

    def display(self):
        return self.person().name() + "'s Bills Sponsored"
        
class BillFeed(OneArgFeed):
    prefix = "bill"

class IssueFeed(OneArgFeed):
    prefix = "crs"
    
class CommitteeFeed(OneArgFeed):
    prefix = "committee"
    def __init__(self, arg):
        self.arg = arg
        self.committee = Committee.objects.get(code=self.arg)
        self.localname = self.committee.name
    def expand(self):
        return [self] + [CommitteeFeed(s.code) for s in self.committee.subcommittees.all()]

class DistrictFeed(OneArgFeed):
    prefix = "district"

class ActiveBillsFeed(NoArgFeed):
    name = "misc:activebills"
    
class EnactedBillsFeed(NoArgFeed):
    name = "misc:enactedbills"

class IntroducedBillsFeed(NoArgFeed):
    name = "misc:introducedbills"

class ActiveBills2Feed(NoArgFeed):
    name = "misc:activebills2"

class AllCommitteesFeed(NoArgFeed):
    name = "misc:allcommittee"

class AllVotesFeed(NoArgFeed):
    name = "misc:allvotes"
    
for clz in (eval(x) for x in dir()):
    if isinstance(clz, type) and issubclass(clz, NoArgFeed):
        NoArgFeed.feedmap[clz.name] = clz
    if isinstance(clz, type) and issubclass(clz, OneArgFeed):
        OneArgFeed.feedmap[clz.prefix] = clz


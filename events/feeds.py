# This module defines the metadata of Feeds, which are collections of tracked events.
# Each feed has a name (getname()), which is an encoded string such as p:400001, and
# other metadata such as a title (gettitle()).
#
# The association between events and feeds is created by the objects that create the event
# records.
#
# The localname field of a feed is used to display the feed name when it is grouped with
# other related fields.
#
# Feed.get_events() and Feed.get_events_for(feeds) returns a QuerySet over events
# that match the feed(s).
#
# Feed.from_name(name) returns a Feed object from a feed name (e.g. again p:400001).

from django.db.models.query import QuerySet

from person.models import Person
from committee.models import Committee
from events import models

class Feed(object):
    @staticmethod
    def from_name(name):
        if name in NoArgFeed.feedmap:
            return NoArgFeed.feedmap[name]()
        
        args = name.split(":")
        if args[0] in OneArgFeed.feedmap:
            clz = OneArgFeed.feedmap[args[0]]
            return clz(":".join(args[1:]))
            
        raise ValueError("Invalid feed: " + name)
        
    def expand(self):
        return [self]
        
    @staticmethod
    def get_events_for(feeds):
        qs = models.Event.objects.all()
        qs = qs.order_by("-when")
        
        if feeds != None:
            fd = []
            for f1 in feeds:
                for f2 in f1.expand():
                    fd.append(f2.getname())
            qs = qs.filter(feed__feedname__in=fd)
        
        # because events can occur in multiple feeds, we need to
        # run a projection & distinct on a subset of the fields, and the
        # only way to do that is through values() which causes the
        # iterations to return dicts rather than Events.
        qs = qs.values("source_content_type", "source_object_id", "eventid", "when").distinct()
        
        return qs
        
    def get_events(self):
        return Feed.get_events_for((self,))

class NoArgFeed(Feed):
    feedmap = { }
    
    name = None
    
    def __unicode__(self):
        return self.name

    def getname(self):
        return self.name
    def gettitle(self):
        return self.title
    
class OneArgFeed(Feed):
    feedmap = { }
    
    prefix = None
    arg = None
    
    def __init__(self, arg):
        self.arg = arg
    
    def getname(self):
        return self.prefix + ":" + str(self.arg)

    def __unicode__(self):
        return self.name()

class PersonFeed(OneArgFeed):
    prefix = "p"
    _person = None
    
    def person(self):
        if self._person == None:
            self._person = Person.objects.get(id=int(self.arg))
        return self._person
        
    def gettitle(self):
        return self.person().name
        
    def expand(self):
        if self.__class__ == PersonFeed:
            return [self, PersonVotesFeed(self.arg), PersonSponsorshipFeed(self.arg)]
        else:
            return [self]

class PersonVotesFeed(PersonFeed):
    prefix = "pv"
    localname = "Voting Record"

    def gettitle(self):
        return self.person().name() + "'s Voting Record"

class PersonSponsorshipFeed(PersonFeed):
    prefix = "ps"
    localname = "Bills Sponsored"

    def gettitle(self):
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
    title = "All Activity on Legislation"
    
class EnactedBillsFeed(NoArgFeed):
    name = "misc:enactedbills"
    title = "Enacted Bills"

class IntroducedBillsFeed(NoArgFeed):
    name = "misc:introducedbills"
    title = "Introduced Bills and Resolutions"

class ActiveBills2Feed(NoArgFeed):
    name = "misc:activebills2"

class AllCommitteesFeed(NoArgFeed):
    name = "misc:allcommittee"
    title = "Upcoming Committee Meetings"

class AllVotesFeed(NoArgFeed):
    name = "misc:allvotes"
    title = "All Roll Call Votes"
    
# Record the feed names and prefixes defined in the classes in two dicts so
# that feed names can be quickly parsed.
for clz in (eval(x) for x in dir()):
    if isinstance(clz, type) and issubclass(clz, NoArgFeed):
        NoArgFeed.feedmap[clz.name] = clz
    if isinstance(clz, type) and issubclass(clz, OneArgFeed):
        OneArgFeed.feedmap[clz.prefix] = clz


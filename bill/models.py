# -*- coding: utf-8 -*-
from django.db import models

from common import enum
from common.fields import JSONField

from committee.models import Committee
from bill.status import BillStatus

"Enums"

class BillType(enum.Enum):
    house_resolution = enum.Item(1, 'H.Res.', slug='hres', xml_code='hr')
    senate = enum.Item(2, 'S', slug='s', xml_code='s')
    house_of_representatives = enum.Item(3, 'H.R.', slug='hr', xml_code='h')
    senate_resolution = enum.Item(4, 'S.Res.', slug='sr', xml_code='sr')
    house_concurrent_resolution = enum.Item(5, 'H.Con.Res.', slug='hc', xml_code='hc')
    senate_concurrent_resolution = enum.Item(6, 'S.Con.Res.', slug='sc', xml_code='sc')
    house_joint_resolution = enum.Item(7, 'H.J.Res.', slug='hj', xml_code='hj')
    senate_joint_resolution = enum.Item(8, 'S.J.Res.', slug='sj', xml_code='sj')


class TermType(enum.Enum):
    old = enum.Item(1, 'Old')
    new = enum.Item(2, 'New')

"Models"

class BillTerm(models.Model):
    """
    Bill Term aka Issua Area

    Old terms:
     * http://www.govtrack.us/data/us/liv.xml
    New terms:
     * http://www.govtrack.us/data/us/liv111.xml
     * http://www.govtrack.us/data/us/crsnet.xml
    """
    name = models.CharField(max_length=255)
    parent = models.ForeignKey('bill.BillTerm', blank=True, null=True)
    term_type = models.IntegerField(choices=TermType)

    def __unicode__(self):
        return self.name

    class Meta:
        unique_together = ('name', 'parent', 'term_type')


class Cosponsor(models.Model):
    person = models.ForeignKey('person.Person')
    bill = models.ForeignKey('bill.Bill')
    joined = models.DateField()
    withdrawn = models.DateField(blank=True, null=True)


class Bill(models.Model):
    title = models.CharField(max_length=255)
    # Serialized list of all bill titles
    titles = JSONField()
    bill_type = models.IntegerField(choices=BillType)
    congress = models.IntegerField()
    number = models.IntegerField()
    sponsor = models.ForeignKey('person.Person', blank=True, null=True,
                                related_name='sponsored_bills')
    committees = models.ManyToManyField(Committee, related_name='bills')
    terms = models.ManyToManyField(BillTerm, related_name='bills')
    current_status = models.IntegerField(choices=BillStatus)
    current_status_date = models.DateField()
    introduced_date = models.DateField()
    cosponsors = models.ManyToManyField('person.Person', blank=True, through='bill.Cosponsor')

    def __unicode__(self):
        return self.title

    class Meta:
        ordering = ('congress', 'bill_type', 'number')
        unique_together = ('congress', 'bill_type', 'number')
        
    def create_events(self, actions):
        from events.feeds import PersonSponsorshipFeed, BillFeed, IssueFeed, CommitteeFeed, ActiveBillsFeed, EnactedBillsFeed, IntroducedBillsFeed, ActiveBillsExceptIntroductionsFeed 
        from events.models import Event
        with Event.update(self) as E:
            index_feeds = [BillFeed(self)]
            if self.sponsor != None:
                index_feeds.append(PersonSponsorshipFeed(self.sponsor))
            index_feeds.extend([IssueFeed(ix) for ix in self.terms.all()])
            index_feeds.extend([CommitteeFeed(cx) for cx in self.committees.all()])
            
            E.add("state:" + str(BillStatus.introduced), self.introduced_date, index_feeds + [ActiveBillsFeed(), IntroducedBillsFeed()])
            for date, state, text in actions:
                if state == BillStatus.introduced:
                    continue # already indexed
                E.add("state:" + str(state), date, index_feeds + [ActiveBillsFeed(), ActiveBillsExceptIntroductionsFeed()])
	
    def render_event(self, eventid, feeds):
        import events.feeds
        return {
            "type": "Vote",
            "date": self.created,
            "title": self.question,
			"url": self.get_absolute_url(),
            "body_text_template":
"""{{summary|safe}}
{% for voter in voters %}
    {{voter.name|safe}}: {{voter.vote|safe}}
{% endfor %}""",
            "body_html_template":
"""<p>{{summary}}</p>
{% for voter in voters %}
    {% if forloop.first %}<ul>{% endif %}
    <p><a href="{{voter.url}}">{{voter.name}}</a>: {{voter.vote}}</p>
    {% if forloop.last %}</ul>{% endif %}
{% endfor %}
""",
            "context": {
                "summary": self.summary(),
                "voters":
                            [
                                { "url": f.person().get_absolute_url(), "name": f.person().name, "vote": self.voters.get(person=f.person()).option.value }
                                for f in feeds if isinstance(f, events.feeds.PersonFeed) and self.voters.filter(person=f.person()).exists()
                            ]
                        if feeds != None else []
                }
            }
        

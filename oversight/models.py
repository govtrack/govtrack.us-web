import re

from django.db import models
from django.conf import settings
from django.core.cache import cache

from person.models import Person
from committee.models import Committee
from bill.models import Bill

from website.templatetags.govtrack_utils import markdown
from events.models import truncate_words

class OversightTopic(models.Model):
    """An oversight/investigation topic."""

    title = models.CharField(max_length=256, help_text="The title oversight topic for display purposes.")
    slug = models.SlugField(help_text="The slug used in URLs for this topic.")

    congress_start = models.IntegerField(default=settings.CURRENT_CONGRESS, help_text="The first Congress this oversight topic pertained to.")
    congress_end = models.IntegerField(default=settings.CURRENT_CONGRESS, help_text="The last Congress this oversight topic pertained to, after which the topic is hidden from the main list.")

    summary = models.CharField(max_length=256, help_text="One-sentence explaining what the topic is about.")
    current_status = models.CharField(max_length=256, help_text="One-sentence explaining what the current status of this topic is.")
    next_step = models.CharField(max_length=256, help_text="One-sentence explaining what the next procedural steps or expected actions for this topic are.")
    narrative = models.TextField(blank=True, help_text="The long explanatory text for the topic in CommonMark format.")
    post_date = models.DateTimeField(help_text="The date this oversight topic's summary was last updated.")

    related_oversight_topics = models.ManyToManyField('self', blank=True, help_text="Other OversightTopics that are related.")
    
    created = models.DateTimeField(db_index=True, auto_now_add=True, help_text="The date the oversight topic was created.")
    updated = models.DateTimeField(db_index=True, auto_now=True, help_text="The date the oversight topic's record was last saved.")

    class Meta:
        ordering = ["-created"]

    def __repr__(self):
        return "<OversightTopic [{}] {}>".format(self.id, self.title[:45])

    def get_absolute_url(self):
        return "/congress/oversight/{}-{}".format(self.id, self.slug)

    def narrative_as_html(self):
        # Demote headings.
        narrative = markdown(self.narrative)
        narrative = re.sub(r"(</?[Hh])(\d)(>)",
                           lambda m : m.group(1) + str(int(m.group(2))+2) + m.group(3),
                           narrative)
        return narrative

    def narrative_as_plain_text(self):
        # Make links nicer.
        return re.sub("\[(.*?)\]\(.*?\)", r"\1", self.narrative)

    @staticmethod
    def get_overview_feed():
        from events.models import Feed
        return Feed.objects.get_or_create(feedname="misc:oversight")[0]

    def get_feed(self):
        from events.models import Feed
        return Feed.objects.get_or_create(feedname="%s:%d" % ("oversight", self.id))[0]

    @staticmethod
    def from_feed(feed):
        if ":" not in feed.feedname or feed.feedname.split(":")[0] not in ("oversight",): raise ValueError(feed.feedname)
        id = int(feed.feedname.split(":")[1])
        cache_key = "oversight:%d" % id
        obj = cache.get(cache_key)
        if not obj:
            obj = OversightTopic.objects.get(id=id)
            cache.set(cache_key, obj, 60*60*4) # 4 hours
        return obj

    def create_events(self):
        from events.models import Feed, Event
        with Event.update(self) as E:
            # Events for this topic get into the feed for this topic, the overall
            # oversight feed, and the feeds for related people, bills, and committees.
            index_feeds = [self.get_overview_feed(), self.get_feed()]
            for rec in self.relevant_people.all():
                index_feeds.append(rec.person.get_feed())
            for rec in self.relevant_bills.all():
                index_feeds.append(rec.bill.get_feed())
            for rec in self.relevant_committees.all():
                index_feeds.append(rec.committee.get_feed())

            # Add events.
            E.add("initial", self.created, index_feeds)
            for update in self.updates.order_by('created'):
                E.add("update:{}".format(update.id), update.created, index_feeds)

    def render_event(self, eventid, feeds):
        if eventid == "initial":
            return self.render_event_initial(feeds)
        if ":" in eventid:
            ev_type, ev_code = eventid.split(":")
            if ev_type == "update":
                return self.render_event_update(ev_code, feeds)
        raise Exception()

    def render_event_initial(self, feeds):
        return {
            "type": "Oversight & Investigations",
            "date": self.created,
            "date_has_no_time": False,
            "title": self.title,
            "url": self.get_absolute_url(),
            "body_text_template": "{{text|safe}}",
            "body_html_template": "{{html|safe}}",
            "context": {
                "text": truncate_words(self.narrative_as_plain_text(), 300),
                "html": truncate_words(self.narrative_as_html(), 300),
            },
            "thumbnail_url": None,
        }

    def render_event_update(self, event_id, feeds):
        update = self.updates.get(id=event_id)
        return {
            "type": "Oversight & Investigations",
            "date": update.created,
            "date_has_no_time": False,
            "title": update.title,
            "url": self.get_absolute_url(),
            "body_text_template": "{{text|safe}}",
            "body_html_template": "{{html|safe}}",
            "context": {
                "text": update.summary_as_plain_text(),
                "html": update.summary_as_html(),
            },
            "thumbnail_url": None,
        }

class OversightRelevantPerson(models.Model):
    """A link between an OversightTopic and a Person."""
    topic = models.ForeignKey(OversightTopic, related_name="relevant_people", help_text="The related topic.")
    person = models.ForeignKey(Person, related_name="oversight_topics", help_text="The related person.")
    description = models.CharField(max_length=256, blank=True, help_text="One-sentence explaining how the person relates to the topic. The sentence must be able to stand on its own because it will appear on both the oversight topic page and the person's page.")
    order = models.IntegerField(default=0, help_text="If different order numbers are given to relevant bills, they will be listed in ascending numeric order by this field.")
    class Meta:
        unique_together = [("topic", "person")]
        ordering = ["order"] # controls order on topic pages

class OversightRelevantBill(models.Model):
    """A link between an OversightTopic and a Bill."""
    topic = models.ForeignKey(OversightTopic, related_name="relevant_bills", help_text="The related topic.")
    bill = models.ForeignKey(Bill, related_name="oversight_topics", help_text="The related bill.")
    description = models.CharField(max_length=256, blank=True, help_text="One-sentence explaining how the bill relates to the topic. The sentence must be able to stand on its own because it will appear on both the oversight topic page and the bill's page.")
    order = models.IntegerField(default=0, help_text="If different order numbers are given to relevant bills, they will be listed in ascending numeric order by this field.")
    class Meta:
        unique_together = [("topic", "bill")]
        ordering = ["order"] # controls order on topic pages

class OversightRelevantCommittee(models.Model):
    """A link between an OversightTopic and a Bill."""
    topic = models.ForeignKey(OversightTopic, related_name="relevant_committees", help_text="The related topic.")
    committee = models.ForeignKey(Committee, related_name="oversight_topics", help_text="The related committee.")
    description = models.CharField(max_length=256, blank=True, help_text="One-sentence explaining how the committee relates to the topic. The sentence must be able to stand on its own because it will appear on both the oversight topic page and the committee's page.")
    order = models.IntegerField(default=0, help_text="If different order numbers are given to relevant bills, they will be listed in ascending numeric order by this field.")
    class Meta:
        unique_together = [("topic", "committee")]
        ordering = ["order"] # controls order on topic pages

class OversightUpdate(models.Model):
    """An update for the oversight topic for a timeline or that we might send out in an email update."""
    topic = models.ForeignKey(OversightTopic, related_name="updates", help_text="The related topic.")
    title = models.CharField(max_length=256, help_text="The title oversight topic for display purposes.")
    summary = models.TextField(help_text="The summary text for the topic in CommonMark format.")
    created = models.DateTimeField(db_index=True, auto_now_add=True, help_text="The date the oversight topic was created.")
    updated = models.DateTimeField(db_index=True, auto_now=True, help_text="The date the oversight topic's metadata/summary was last updated.")

    class Meta:
        ordering = ["-created"] # controls order on topic pages

    def summary_as_html(self):
        return markdown(self.summary)

    def summary_as_plain_text(self):
        # Make links nicer.
        return re.sub("\[(.*?)\]\(.*?\)", r"\1", self.summary)

from events.models import Feed
Feed.register_feed(
    "misc:oversight",
    title = "Congressional Oversight & Investigations",
    simple = True,
    slug = "oversight",
    intro_html = """<p>This feed includes all actions we are tracking on congressional oversight.</p>""",
    category = "oversight",
    description = "You will get updates when there are major congressional actions related to oversight of the executive branch.",
    )
Feed.register_feed(
    "oversight:",
    title = lambda feed : OversightTopic.from_feed(feed).title,
    noun = "oversight topic",
    link = lambda feed: OversightTopic.from_feed(feed).get_absolute_url(),
    category = "oversight",
    description = "You will get updates when there are major congressional actions related to this oversight topic.",
    )
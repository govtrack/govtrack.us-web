from django.db import models
from django.contrib.auth.models import User
from django.conf import settings

import re
from jsonfield import JSONField
from markdownx.models import MarkdownxField

from events.models import Feed, SubscriptionList

class UserProfile(models.Model):
    user = models.OneToOneField(User, db_index=True, on_delete=models.CASCADE)
    massemail = models.BooleanField(default=True) # may we send you mail?
    massemail_options = models.CharField(max_length=128, default="", blank=True)
    old_id = models.IntegerField(blank=True, null=True) # from the pre-2012 GovTrack database
    last_mass_email = models.IntegerField(default=0)
    last_blog_post_emailed = models.IntegerField(default=0)
    congressionaldistrict = models.CharField(max_length=4, blank=True, null=True, db_index=True) # or 'XX00' if the user doesn't want to provide it

    # monetization
    paid_features = JSONField(default={}, blank=True, null=True) # maps feature name to tuple (payment ID, sale ID or None if not useful)

    # bulk messages - one-click unsubscribe keys
    one_click_unsub_key = models.CharField(max_length=64, blank=True, null=True, db_index=True, unique=True)
    one_click_unsub_gendate = models.DateTimeField(blank=True, null=True)
    one_click_unsub_hit = models.DateTimeField(blank=True, null=True)

    # we ask people after a long term period of inactivity if they still want to hear from us,
    # and this records the date we sent the warning
    inactivity_warning_sent = models.DateTimeField(blank=True, null=True)

    # for the constituent calls research project
    research_anon_key = models.IntegerField(blank=True, null=True, unique=True)

    # since some permissions depend on the user's email address, we must re-confirm people's
    # email addresses periodically
    pending_email_reconfirmation = models.DateTimeField(blank=True, null=True)
    email_reconfirmed_at = models.DateTimeField(blank=True, null=True)

    def lists(self):
        # make sure the 'default' list exists
        SubscriptionList.objects.get_or_create(
            user = self.user,
            is_default = True,
            defaults = { "name": "Email Updates" , "email": 1 } )
        return SubscriptionList.objects.filter(user=self.user).order_by('name')
    def lists_with_email(self):
        # return lists with trackers with email updates turned on
        return SubscriptionList.objects.filter(user=self.user, email__gt=0, trackers__id__gt=0).distinct().order_by('name')

    def get_membership_subscription_info(self):
        from datetime import datetime, timedelta

        ret = {
            "active": False,
        }
        
        if self.paid_features and self.paid_features.get("ad_free"):
            ad_free = self.paid_features['ad_free']
            from parser.processor import Processor
            created = Processor.parse_datetime(ad_free["date"])
            expires = Processor.parse_datetime(ad_free["expires"]) if ad_free["expires"] is not None else None
            #pmt = PayPalPayment.objects.get(paypal_id = ad_free["paypal_payment_id])
            #expires = pmt.created.replace(year=pmt.created.year+1)
            if expires is None:
                ret["active"] = True
                ret["message"] = "You went ad-free for life on %s. Thanks!" % created.strftime("%x")
            elif expires >= datetime.now():
                ret["active"] = True
                if created > (datetime.now() - timedelta(days=0.5)):
                    # User just took this action.
                    ret["message"] = "Thanks for your one-year membership subscription which expires on %s." % expires.strftime("%x")
                else:
                    ret["message"] = "You started your membership subscription on %s. Your subscription expires on %s. Thanks!" % (created.strftime("%x"), expires.strftime("%x"))
            else:
                ret["message"] = "Your membership subscription expired on %s." % expires.strftime("%x")

        return ret

    def get_one_click_unsub_key(self):
        # Get the current one-click unsubscribe key for a user. If no key is set or
        # a key is out of date, generate a fresh key.
        from datetime import datetime, timedelta
        import random, string
        if (not self.one_click_unsub_key) or (datetime.now() - self.one_click_unsub_gendate > timedelta(days=60)):
            self.one_click_unsub_key = ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(20))
            self.one_click_unsub_gendate = datetime.now()
            self.save(update_fields=['one_click_unsub_key', 'one_click_unsub_gendate'])
        return self.one_click_unsub_key
    def get_one_click_unsub_url(self):
        return settings.SITE_ROOT_URL + "/accounts/unsubscribe/" + self.get_one_click_unsub_key()

    @staticmethod
    def one_click_unsubscribe(key):
        from datetime import datetime, timedelta
        if key.strip() == "":
            return False # empty key, nice try
        try:
            p = UserProfile.objects.get(one_click_unsub_key=key)
        except UserProfile.DoesNotExist:
            return False # invalid key
        if (p.one_click_unsub_gendate is None) or (datetime.now() - p.one_click_unsub_gendate > timedelta(days=60)):
            return False # expired (plus sanity check)

        # Ok, unsubscribe from mass emails.
        p.massemail = False
        p.one_click_unsub_hit = datetime.now()
        p.save(update_fields=['massemail', 'one_click_unsub_hit'])

        # And all lists.
        SubscriptionList.objects.filter(user=p.user).update(email=0)

        return True

    def is_inactive(self):
        return self.inactivity_warning_sent and (not self.user.last_login or self.user.last_login < self.inactivity_warning_sent)

    def get_blogpost_categories(self):
        unsubscribed_categories = {
            key.split(":")[1]
            for key in self.massemail_options.split(",")
            if key.startswith("unsubcat:")
        }
        for cat in BlogPost.get_categories_with_freq():
            if not self.massemail:
                cat["subscribed"] = False
            else:
                cat["subscribed"] = cat["key"] not in unsubscribed_categories
            yield cat

    def get_blogpost_freq(self):
        for key in self.massemail_options.split(","):
            if key.startswith("postfreq:"):
                return key[len("postfreq:"):]
        return None

def get_user_profile(user):
    if hasattr(user, "_profile"): return user._profile
    profile, isnew = UserProfile.objects.get_or_create(user = user)
    user._profile = profile
    return profile
User.userprofile = get_user_profile 
    
class CampaignSupporter(models.Model):
    campaign = models.CharField(max_length=96)
    prefix = models.CharField(max_length=96)
    firstname = models.CharField(max_length=96)
    lastname = models.CharField(max_length=96)
    address = models.CharField(max_length=96)
    city = models.CharField(max_length=96)
    state = models.CharField(max_length=96)
    zipcode = models.CharField(max_length=96)
    email = models.CharField(max_length=96)
    message = models.CharField(max_length=256, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    district = models.IntegerField(blank=True, null=True)
    geocode_response = models.TextField(blank=True, null=True)
   
class Req(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    request = models.TextField()

from bill.models import Bill
class CommunityInterest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE)
    methods = models.CharField(max_length=32)
    created = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ( ('user', 'bill'), )

class PayPalPayment(models.Model):
    paypal_id = models.CharField(max_length=64, db_index=True)
    user = models.ForeignKey(User, blank=True, null=True, db_index=True, on_delete=models.PROTECT)
    response_data = JSONField()
    executed = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    notes = models.CharField(max_length=64)
    
    class Meta:
        unique_together = ( ('user', 'created'), ) # dangerous?

    @staticmethod
    def from_session(request):
        import paypalrestsdk
        try:
            payment_id = request.session["paypal-payment-to-execute"]
            del request.session["paypal-payment-to-execute"]
        except KeyError:
            raise ValueError("User session lost track of payment object." )

        payment = paypalrestsdk.Payment.find(payment_id)

        try:
            rec = PayPalPayment.objects.get(paypal_id = payment.id)
        except PayPalPayment.DoesNotExist:
            raise ValueError("Trying to complete a payment that does not exist in our database: " + payment.id)
    
        return (payment, rec)

    @staticmethod
    def execute(request):
        # Get object.
        (payment, rec) = PayPalPayment.from_session(request)
        
        # Execute if it's not already been executed (in case of page reload).
        if payment.state == "created" and not rec.executed:
            if not payment.execute({"payer_id": request.GET["PayerID"]}):
                raise ValueError("Error executing PayPal.Payment (%s): " % (payment.id, repr(payment.error)))
            
        # Update our database record of the payment.
        rec.response_data = payment.to_dict()
        rec.executed = True
        rec.save()
        
        return (payment, rec)

class MediumPost(models.Model):
    medium_id = models.CharField(max_length=32, unique=True)
    title = models.CharField(max_length=128)
    collection_slug = models.CharField(max_length=128)
    post_slug = models.CharField(max_length=128)

    data = JSONField(default={})

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    published = models.DateTimeField(db_index=True)

    def get_absolute_url(self):
        return "/medium-post-redirector/" + str(self.id)

    @property
    def url(self):
        return "https://medium.com/" + self.collection_slug + "/" + self.post_slug

    @staticmethod
    def get_medium_posts():
        import urllib.request, urllib.error, urllib.parse, json
        # Fetch posts.
        medium_posts = urllib.request.Request("https://medium.com/govtrack-insider?format=json")
        medium_posts.add_header("User-Agent", "Python +https://www.govtrack.us") # default header has been blocked
        medium_posts = urllib.request.urlopen(medium_posts).read().decode("utf8")
        # there's some crap before the JSON object starts
        medium_posts = medium_posts[medium_posts.index("{"):]
        medium_posts = json.loads(medium_posts)
        for section in medium_posts['payload']['streamItems']:
            for post in section["section"]["items"]:
                post = medium_posts['payload']['references']['Post'][post["post"]["postId"]]
                collection = medium_posts['payload']['references']['Collection'][post['homeCollectionId']]
                post["homeCollection"] = collection
                yield post

    @staticmethod
    def sync():
        # Sync posts with our model instances.
        for post in MediumPost.get_medium_posts():
            MediumPost.syncitem(post)

    @staticmethod
    def syncitem(post):
        from datetime import datetime

        try:
            obj = MediumPost.objects.get(medium_id=post['id'])
        except MediumPost.DoesNotExist:
            # get_or_create fails b/c we have to supply required fields
            obj = MediumPost(medium_id=post['id'])

        obj.title = post['title']
        obj.collection_slug = post["homeCollection"]['slug']
        obj.post_slug = post['uniqueSlug']
        obj.data = post
        obj.published = datetime.fromtimestamp(post['firstPublishedAt']/1000)

        # MySQL can't hold four-byte UTF8 characters. Supposedly a different
        # charset will work (alter table website_mediumpost modify title varchar(128) character set utf8mb4 not null;)
        # but even with this we still get an Incorrect string value error
        # trying to save a four-byte emoji. So just kill those characters.
        obj.title = "".join(c for c in str(obj.title) if len(c.encode("utf8")) < 4)

        obj.save()

        obj.create_events()

    @property
    def publish_date_display(self):
        return self.data['virtuals']['firstPublishedAtEnglish']

    @property
    def snippet(self):
        return self.data['virtuals'].get('subtitle')

    @property
    def image_url(self):
        return self.image_400px

    @property
    def image_100px(self):
        return self.get_image_url(100)

    @property
    def image_400px(self):
        return self.get_image_url(400)

    def get_image_url(self, size): # 100, 400
        if self.data['virtuals'].get('previewImage', {}).get("imageId"):
            return "https://cdn-images-1.medium.com/max/" + str(size) + "/" + self.data['virtuals']['previewImage']['imageId']
        return None

    def create_events(self):
        from events.models import Feed, Event
        with Event.update(self) as E:
            feeds = [Feed.from_name("misc:govtrackinsider")]
            E.add("post", self.published, feeds)

    def render_event(self, eventid, feeds):
        return {
            "type": "GovTrack Insider",
            "date": self.published,
            "date_has_no_time": False,
            "title": self.title,
            "url": self.get_absolute_url(),
            "body_text_template": """{{snippet|safe}}""",
            "body_html_template": """<p>{{snippet}}</p>""",
            "context": {
                "snippet": self.snippet,
                },
            "thumbnail_url": self.get_image_url(100),
            }

Feed.register_feed(
    "misc:govtrackinsider",
    title = "GovTrack Insider Articles",
    simple = True,
    slug = "govtrack-insider",
    intro_html = """<p>This feed includes posts on <a href="https://medium.com/govtrack-insider">GovTrack Insider</a>.</p>""",
    description = "Get an update whenever we post a new article on GovTrack Insider.",
    )

class Reaction(models.Model):
    subject = models.CharField(max_length=20, db_index=True)
    user = models.ForeignKey(User, blank=True, null=True, db_index=True, on_delete=models.CASCADE)
    anon_session_key = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    reaction = JSONField()
    extra = JSONField()

    created = models.DateTimeField(auto_now_add=True, db_index=True)

    EMOJI_CHOICES = [
        'smile', 'scream', 'hugging', 'rage', 'ok_hand', 'clap',
        'chart_with_downwards_trend', 'broken_heart', '100', 'turtle',
        'hamburger', 'baseball', 'money_mouth', 'statue_of_liberty',
    ]
    
    class Meta:
        unique_together = ( ('subject', 'user'), ('subject', 'anon_session_key') ) 

    @staticmethod
    def get_session_key(request):
        import random, string
        return request.session.setdefault("reactions-key",
            ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(20))
            )

    @staticmethod
    def get_for_user(request):
        if request.user.is_authenticated:
            return Reaction.objects.filter(user=request.user)
        elif "reactions-key" in request.session:
            return Reaction.objects.filter(anon_session_key=Reaction.get_session_key(request))
        else:
            return Reaction.objects.none()


class UserPosition(models.Model):
    subject = models.CharField(max_length=20, db_index=True)
    user = models.ForeignKey(User, blank=True, null=True, db_index=True, on_delete=models.CASCADE)
    likert = models.IntegerField(blank=True, null=True)
    reason = models.TextField(blank=True)
    extra = JSONField()

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ( ('subject', 'user'), )

    def get_subject_link(self):
        return Feed.from_name(self.subject).link
    def get_subject_title(self):
        return Feed.from_name(self.subject).title


class Sousveillance(models.Model):
    subject = models.CharField(max_length=24, db_index=True)
    user = models.ForeignKey(User, blank=True, null=True, db_index=True, on_delete=models.CASCADE)
    req = JSONField()
    when = models.DateTimeField(auto_now_add=True, db_index=True)


class UserGroupSignup(models.Model):
    user = models.ForeignKey(User, blank=True, null=True, db_index=True, on_delete=models.CASCADE)
    email = models.CharField(max_length=256, blank=True, null=True)
    groups = models.CharField(max_length=256, blank=True, null=True)
    when = models.DateTimeField(auto_now_add=True, db_index=True)


class Community(models.Model):
    slug = models.SlugField()
    name = models.CharField(max_length=256, help_text="The display name of the community.")
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    access_explanation = models.TextField(help_text="Displayed below the post form to let the user know who can read the post.")
    login_teaser = models.TextField(help_text="Teaser text to get an anonymous user to log in to post. Applicable if the community is based on an IP-range.")
    post_teaser = models.TextField(help_text="Teaser text to get a logged in user to open the post form.")
    author_display_field_label = models.TextField(help_text="The text to use for the form field label for the author_display field, which is a signature line for the author, recognizing that a person's name, title, and organization can change over time without a change in user account or email address.")

    def __str__(self): return "{} ({})".format(self.name, self.slug)

    class Meta:
    	verbose_name_plural = "Communities"

class CommunityMessageBoard(models.Model):
    community = models.ForeignKey(Community, on_delete=models.PROTECT, help_text="The community that has acccess to read and post to this board.")
    subject = models.CharField(max_length=20, db_index=True, help_text="A code for the topic of the board, i.e. where the board appears on the website.")
    created = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self): return self.get_subject_title()

    def get_subject_link(self):
        return Feed.from_name(self.subject, must_exist=False).link
    def get_subject_title(self):
        return Feed.from_name(self.subject, must_exist=False).title

class CommunityMessage(models.Model):
    board = models.ForeignKey(CommunityMessageBoard, on_delete=models.PROTECT, help_text="The board that this message is a part of.")
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    author_display = models.TextField(help_text="A signature line for the author, recognizing that a person's name, title, and organization can change over time without a change in user account or email address.")
    message = models.TextField()
    history = JSONField(help_text="The history of edits to this post as a list of dicts holding previous field values.")
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
    	index_together = [("board", "modified")]

    def push_message_state(self):
        if not isinstance(self.history, list): self.history = []
        self.history.append({ "author_display": self.author_display, "message": self.message, "modified": self.modified.isoformat() })
        self.save(update_fields=["history"])

    @property
    def has_been_edited(self):
    	return bool(self.history)

class IpAddrInfo(models.Model):
    ipaddr = models.GenericIPAddressField(db_index=True, unique=True)
    first_hit = models.DateTimeField(auto_now_add=True)
    last_hit = models.DateTimeField(auto_now=True, db_index=True)
    hits = models.IntegerField(default=1, db_index=True)
    leadfeeder = JSONField(default={}, blank=True, null=True)

class BlogPost(models.Model):
    CATEGORIES = [
        ("sitenews", "News About GovTrack"),
        ("sitehelp", "Using GovTrack Tips"),
        ("analysis", "Analysis and Commentary"),
        ("billsumm", "Bill Summary"),
        ("legrecap", "Legislative Recap"),
        ("legahead", "Legislative Preview"),
    ]

    title = models.CharField(max_length=128)
    category = models.CharField(max_length=24, blank=True, null=True,
        choices=[(None, "Not Set")] + CATEGORIES)
    author = models.CharField(max_length=128, blank=True, null=True)
    body = MarkdownxField()
    info = JSONField(default={}, blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    published = models.BooleanField(default=False, db_index=True)

    class Meta:
        index_together = [("published", "created"),
                          ("published", "category", "created")]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        from django.template.defaultfilters import slugify
        if not self.published: return "/posts"
        return "/posts/{}/{}_{}".format(self.id, self.created.date().isoformat(), slugify(self.title))

    def body_preview_html(self):
        # Remove images before character truncation.
        text = re.sub(r"!\[(.*?)\]\((.*?)\)", r"", self.body)

        # Truncate plain text at a word boundary.
        # After this point, for some reasonn the Markdown renderer
        # doesn't always render and leaves everything as Markdown.
        from django.utils.text import Truncator
        text = Truncator(text).words(50, truncate=" ...")

        # Remove any truncated link markup at the end.
        text = re.sub(r"\[([^\]]+ \.\.\.$)", "\1", text)

        # Render to HTML.
        from website.templatetags.govtrack_utils import markdown
        html = markdown(text.strip(), trusted=True)

        # Remove block-level formatting.
        import html5lib, urllib.parse
        valid_tags = set('strong em a code span'.split())
        valid_tags = set('{http://www.w3.org/1999/xhtml}' + tag for tag in valid_tags)
        dom = html5lib.HTMLParser().parseFragment(html)
        for node in dom.iter():
            if node.tag not in valid_tags and node.tag != 'DOCUMENT_FRAGMENT':
                node.tag = '{http://www.w3.org/1999/xhtml}span'
            for name, val in list(node.attrib.items()):
                node.attrib.pop(name)
        html = html5lib.serialize(dom, quote_attr_values="always", omit_optional_tags=False, alphabetical_attributes=True)

        # Remove any straggling links from unrendered Markdown (see above).
        html = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", html)

        return html

    def body_html(self):
        from website.templatetags.govtrack_utils import markdown
        return markdown(self.body, trusted=True)

    def body_text(self):
        # Replace Markdown-style [text][href] links with the text plus bracketed href.
        # Does not handle trusted HTML embedded in Markdown.
        body_text = self.body.strip()
        body_text = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1 at \2", body_text)
        return body_text

    @staticmethod
    def get_categories_with_freq():
        # We're not posting in the billsumm category lately,
        # so no need to let users know about it. We'll
        # also block it in send_email_updates just in case.

        categories = [
            { "key": c[0], "label": c[1], "freq": None, "rawfreq": None }
            for c in BlogPost.CATEGORIES
            if c[0] != "billsumm"
            ]

        from datetime import datetime, timedelta
        for cat in categories:
            qs = BlogPost.objects.filter(published=True, category=cat["key"], created__gt=datetime.now() - timedelta(days=365*2))
            if qs.count() == 0: continue
            n = min(qs.count(), 10)
            p = qs.order_by('-created')[n-1]
            nperday = n / (datetime.now() - p.created).days
            for period, days in (("week", 7), ("month", 30.5), ("year", 365.25)):
               nperperiod = round(nperday * days)
               if nperperiod >= 1:
                   cat['rawfreq'] = nperday
                   cat['freq'] = str(nperperiod) + " per " + period
                   break
        categories = sorted(categories, key = lambda cat : cat["rawfreq"] or 0, reverse=True)
        return categories

    @staticmethod
    def import_wordpress_posts():
        import json, iso8601
        from django.utils.timezone import make_naive
        with open("../medium_scraped_posts_archive.json") as f:
            posts = json.load(f)
        for post in posts:
            for bp in BlogPost.objects.all():
                if bp.info and bp.info["url"] == post["url"]:
                    print("Updating #", bp.id)
                    break
            else:
                print("Adding...", post["title"])
                bp = BlogPost()

            bp.title = post["title"]
            bp.body = post["body"].replace("&nbsp;", " ")
            bp.published = True
            del post["body"]
            bp.info = post
            bp.save()

            # published/modified are updated on save() so can't be directly edited above
            def parse_dt(date_str):
                d = iso8601.parse_date(date_str)
                return make_naive(d)
            BlogPost.objects.filter(id = bp.id).update(
                created = parse_dt(post["published"]),
                updated = parse_dt(post["published"])
            )

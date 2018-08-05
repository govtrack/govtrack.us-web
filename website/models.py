from django.db import models
from django.contrib.auth.models import User

from jsonfield import JSONField

from events.models import Feed, SubscriptionList

class UserProfile(models.Model):
    user = models.OneToOneField(User, db_index=True)
    massemail = models.BooleanField(default=True) # may we send you mail?
    old_id = models.IntegerField(blank=True, null=True) # from the pre-2012 GovTrack database
    last_mass_email = models.IntegerField(default=0)
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
        
        if self.paid_features and self.paid_features.get("ad_free_year"):
            ad_free_pmt = self.paid_features['ad_free_year']
            pmt = PayPalPayment.objects.get(paypal_id = ad_free_pmt[0])
            expires = pmt.created.replace(year=pmt.created.year+1)
            if expires >= datetime.now():
                ret["active"] = True
                if pmt.created > (datetime.now() - timedelta(days=0.5)):
                    # User just took this action.
                    ret["message"] = "Thanks for your one-year membership subscription which expires on %s." % expires.strftime("%x")
                else:
                    ret["message"] = "You started your membership subscription on %s. Your subscription expires on %s. Thanks!" % (pmt.created.strftime("%x"), expires.strftime("%x"))
            else:
                ret["message"] = "Your membership subscription expired on %s." % expires.strftime("%x")

        elif self.paid_features and self.paid_features.get("ad_free_life"):
            ret["active"] = True
            ad_free_pmt = self.paid_features['ad_free_life']
            pmt = PayPalPayment.objects.get(paypal_id = ad_free_pmt[0])
            if pmt.created > (datetime.now() - timedelta(days=0.5)):
                return "Thanks for your subscription to an ad-free GovTrack for life!"
            else:
                return "You went ad-free for life on %s. Thanks!" % pmt.created.strftime("%x")

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
    user = models.ForeignKey(User)
    bill = models.ForeignKey(Bill)
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
        import urllib2, json
        # Fetch posts.
        medium_posts = urllib2.Request("https://medium.com/govtrack-insider?format=json")
        medium_posts.add_header("User-Agent", "Python +https://www.govtrack.us") # default header has been blocked
        medium_posts = urllib2.urlopen(medium_posts).read()
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
        obj.title = "".join(c for c in unicode(obj.title) if len(c.encode("utf8")) < 4)

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


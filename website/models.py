from django.db import models
from django.contrib.auth.models import User

from json_field import JSONField

from events.models import Feed, SubscriptionList

class UserProfile(models.Model):
    user = models.ForeignKey(User, unique=True, db_index=True)
    massemail = models.BooleanField(default=True) # may we send you mail?
    old_id = models.IntegerField(blank=True, null=True) # from the pre-2012 GovTrack database
    last_mass_email = models.IntegerField(default=0)
    
    # monetization
    paid_features = JSONField(default={}, null=True) # maps feature name to tuple (payment ID, sale ID or None if not useful)
    
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

    def get_ad_free_message(self):
        if not self.paid_features: return False

        from datetime import datetime, timedelta
        
        if self.paid_features.get("ad_free_year"):
            ad_free_pmt = self.paid_features['ad_free_year']
            pmt = PayPalPayment.objects.get(paypal_id = ad_free_pmt[0])
            if pmt.created > (datetime.now() - timedelta(days=0.5)):
                return "Thanks for your one-year subscription to an ad-free GovTrack!"
            else:
                return "You went ad-free on %s. Your subscription expires on %s. Thanks!" % (
                	pmt.created.strftime("%x"),
                	pmt.created.replace(year=pmt.created.year+1).strftime("%x") )
        elif self.paid_features.get("ad_free_life"):
            ad_free_pmt = self.paid_features['ad_free_life']
            pmt = PayPalPayment.objects.get(paypal_id = ad_free_pmt[0])
            if pmt.created > (datetime.now() - timedelta(days=0.5)):
                return "Thanks for your subscription to an ad-free GovTrack for life!"
            else:
                return "You went ad-free for life on %s. Thanks!" % pmt.created.strftime("%x")
        else:
            return False
            


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
    user = models.ForeignKey(User, db_index=True, on_delete=models.PROTECT)
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
    
        if payment.state != "created" or rec.executed:
            raise ValueError("Trying to complete an already-executed payment: %s, %s (%s)" + (payment.state, str(rec.executed), payment.id))

        return (payment, rec)

    @staticmethod
    def execute(request, notes_must_match):
        # Get object.
        (payment, rec) = PayPalPayment.from_session(request)
        
        # Validate.
        if rec.notes != notes_must_match:
            raise ValueError("Trying to complete the wrong sort of payment: %s" % payment.id)
            
        # Execute.
        if not payment.execute({"payer_id": request.GET["PayerID"]}):
            raise ValueError("Error executing PayPal.Payment (%s): " + (payment.id, repr(payment.error)))
            
        # Update our database record of the payment.
        rec.response_data = payment.to_dict()
        rec.executed = True
        rec.save()
        
        return (payment, rec)
    


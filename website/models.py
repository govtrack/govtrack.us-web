from django.db import models

from django.contrib.auth.models import User

from events.models import Feed

class UserProfile(models.Model):
    user = models.ForeignKey(User, unique=True, db_index=True)
    
    def lists(self):
        # make sure the 'default' list exists
        SubscriptionList.objects.get_or_create(
            user = self.user,
            is_default = True,
            defaults = { "name": "Email Updates" , "email": 1 } )
        return SubscriptionList.objects.filter(user=self.user).order_by('name')
    
def get_user_profile(user):
    if hasattr(user, "_profile"): return user._profile
    profile, isnew = UserProfile.objects.get_or_create(user = user)
    user._profile = profile
    return profile
User.userprofile = get_user_profile 
    
class SubscriptionList(models.Model):
    user = models.ForeignKey(User, db_index=True)
    name = models.CharField(max_length=64)
    trackers = models.ManyToManyField(Feed)
    is_default = models.BooleanField(default=False)
    email = models.IntegerField(default=0, choices=[(0, 'No Email Updates'), (1, 'Daily Email Updates'), (2, 'Weekly Email Updates')])
    
    class Meta:
        unique_together = [('user', 'name')]

from django.db import models
from django.contrib.auth.models import User

from picklefield import PickledObjectField

class AuthRecord(models.Model):
	# These two fields define a unique AuthRecord: the name of the
	# provider and the identifier the provider uses to identify the
	# user, which if possible should be stable across changes in
	# screen names.
	provider = models.CharField(max_length=32, db_index=True)
	uid = models.CharField(max_length=128)
	
	# The Django User associated with the provider-uid pair.
	user = models.ForeignKey(User, related_name="singlesignon", db_index=True)
	
	# Profile information returned by the most recent OAuth callback, etc.
	auth_token = PickledObjectField()
	profile = PickledObjectField()

	# General metadata.
	created = models.DateTimeField(auto_now_add=True)
	updated = models.DateTimeField(auto_now=True)

	class Meta:
		verbose_name = "Authentication Record"
		unique_together = (("provider", "uid"),)
		# don't add any ordering because it causes mysql filesort on joins

	def __unicode__(self):
		return self.provider + " " + self.uid[0:10] + " -> " + self.user.username
 
class UserProfile(models.Model):
    activation_key = models.CharField(max_length=512)
    key_expires = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, unique=True)

User.profile = property(lambda u: UserProfile.objects.get_or_create(user=u)[0])
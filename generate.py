#!.env/bin/python
from common.system import setup_django
setup_django(__file__)

from django.contrib.auth.models import User

print 'Generating initial data'

try:
    u = User.objects.get(username='foob')
except User.DoesNotExist:
    u = User.objects.create_user('foob', 'foob@foob.com', 'foob')
    u.is_superuser = True
    u.is_staff = True
    u.save()

print 'Created user: %s' % u

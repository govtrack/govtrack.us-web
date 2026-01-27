import os, prctl

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
try:
  prctl.set_name("django-" + os.environ["NAME"])
except:
  pass

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()


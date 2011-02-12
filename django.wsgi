# -*- mode: python -*-

import sys
import os
import os.path
import site

site.addsitedir(os.path.join(os.path.dirname(__file__),
                             '.env', 'lib', 'python2.5', 'site-packages'))

if not os.path.dirname(__file__) in sys.path[:1]:
    sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

from django.core.handlers.wsgi import WSGIHandler
application = WSGIHandler()

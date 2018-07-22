#!/bin/sh
.venv/bin/honcho -e local/settings.env run .venv/bin/uwsgi --wsgi-file wsgi.py --socket /tmp/uwsgi_govtrack_test.sock --chmod-socket=666


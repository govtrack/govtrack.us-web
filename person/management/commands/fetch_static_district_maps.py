from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

import os, os.path
from urllib import urlopen
from PIL import Image

from us import stateapportionment
from person.views import get_district_bounds

image_width = 512
image_height = 512

class Command(BaseCommand):
	def handle(self, *args, **options):
		try:
			os.mkdir("static/images/cd")
		except:
			pass

		for state, app in sorted(stateapportionment.items()):
			if app in ("T", 1):
				self.fetch_static_map(state, 0)
			else:
				self.fetch_static_map(state, 0)
				for cd in range(1, app+1):
					self.fetch_static_map(state, cd)

	def fetch_static_map(self, state, district):

		lat, lng, zoom = get_district_bounds(state, district)

		url = "https://api.mapbox.com/styles/v1/%s/static/%f,%f,%f/%dx%d?access_token=%s" \
			% (settings.MAPBOX_MAP_STYLE, lng, lat, zoom-1, image_width, image_height, settings.MAPBOX_ACCESS_TOKEN)
		fn = "static/images/cd/%s%s.png" % (state, ("%02d" % district) if district != 0 else "")

		if os.path.exists(fn):
			return

		print(state, district, url)

		# Ensure we save a PNG.
		import StringIO
		im = Image.open(StringIO.StringIO(urlopen(url).read()))
		im.save(fn)

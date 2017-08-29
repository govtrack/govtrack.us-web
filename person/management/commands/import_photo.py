from django.core.management.base import BaseCommand, CommandError

from urllib import urlopen
from PIL import Image

from person.models import Person

class Command(BaseCommand):
	def handle(self, *args, **options):
		if len(args) != 4:
			print "Usage: import_photo id url credit_url credit_text"
			return

		id, url, credit_url, credit_text = args

		try:
			p = Person.objects.get(id=id)
		except:
			try:
				p = Person.objects.get(bioguideid=id)
			except:
				print "Invalid id."
				return

		# load photo from url
		import StringIO
		im = Image.open(StringIO.StringIO(urlopen(url).read()))

		ar = 1.2

		if im.size[0] < 200 or im.size[1] < 200*ar:
			raise Exception("image is too small")

		# crop
		if im.size[0]*ar > im.size[1]:
			# too wide
			im = im.crop(box=(int(im.size[0]/2-im.size[1]/ar/2), 0, int(im.size[0]/2+im.size[1]/ar/2), im.size[1]))
		else:
			# too tall
			im = im.crop(box=(0, 0, im.size[0], int(im.size[0]*ar) ))

		def save(im, sz=None):
			fn = "../data/photos/%d%s.jpeg" % (
				p.id,
				"" if not sz else ("-%dpx" % sz))
			if sz is not None:
				im = im.resize((sz, int(sz*ar)), resample=Image.BILINEAR)
			print fn
			im.save(fn)

		# save original and thumbnails
		save(im)
		save(im, 50)
		save(im, 100)
		save(im, 200)

		# write metadata
		with open("../data/photos/%d-credit.txt" % p.id, "w") as f:
			f.write(credit_url + " " + credit_text + "\n")


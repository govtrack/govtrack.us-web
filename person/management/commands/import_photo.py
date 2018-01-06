from django.core.management.base import BaseCommand, CommandError

from urllib import urlopen
from PIL import Image

from person.models import Person

class Command(BaseCommand):
	def add_arguments(self, parser):
		parser.add_argument('person_id')
		parser.add_argument('photo_url')
		parser.add_argument('credit_url')
		parser.add_argument('credit_text')

	def handle(self, *args, **options):
		try:
			p = Person.objects.get(id=options['person_id'])
		except:
			try:
				p = Person.objects.get(bioguideid=options['person_id'])
			except:
				print "Invalid id."
				return

		# load photo from url
		import StringIO
		im = Image.open(StringIO.StringIO(urlopen(options['photo_url']).read()))

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
			f.write(options['credit_url'] + " " + options['credit_text'] + "\n")


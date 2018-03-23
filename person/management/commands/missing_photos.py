from django.core.management.base import BaseCommand, CommandError

from person.models import Person

class Command(BaseCommand):
	def handle(self, *args, **options):
		for p in Person.objects.filter(roles__current=True):
			if not p.has_photo():
				print p.id, p

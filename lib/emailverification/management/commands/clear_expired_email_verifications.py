from django.core.management.base import BaseCommand, CommandError

from emailverification.utils import clear_expired

class Command(BaseCommand):
	args = ''
	help = 'Clears expired verification email records.'
	
	def handle(self, *args, **options):
		clear_expired()


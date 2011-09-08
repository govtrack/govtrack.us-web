from django.core.management.base import BaseCommand, CommandError

from emailverification.utils import resend_verifications

class Command(BaseCommand):
	args = '[test|send]'
	help = 'Re-sends verification emails that have not been clicked or killed after a certain delay, and up to three sends. Specify "test" (or nothing) or "send" on the command line to either print metadata information about what would be sent or actually print metadata and send the emails.'
	
	def handle(self, *args, **options):
		resend_verifications(test=(len(args) != 1 or args[0] != "send"))


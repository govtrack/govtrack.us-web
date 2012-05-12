from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import User
from django.conf import settings

from optparse import make_option

from predictionmarket.models import Market, Outcome, TradingAccount

class Command(BaseCommand):
	args = ''
	help = 'Shows statistics of the most active markets.'
	
	def handle(self, *args, **options):
		bank = TradingAccount.get(User.objects.get(id=settings.PREDICTIONMARKET_BANK_UID))
		
		for market in Market.objects.order_by('-tradecount')[0:10]:
			print market
			for outcome, price in market.prices().items():
				bank_shares = bank.positions(outcome=outcome).get(outcome, { "shares": 0 })["shares"]
				print round(price*100, 1), outcome, "@", outcome.volume-bank_shares, "outstanding shares"
			print

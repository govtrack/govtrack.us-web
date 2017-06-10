from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import User
from django.conf import settings

from optparse import make_option

from bill.models import Bill, BillStatus
from predictionmarket.models import Market, Outcome, Trade, TradingAccount
from bill.prognosis import compute_prognosis

from math import log

class Command(BaseCommand):
	args = ''
	help = 'Make and update prediction markets.'
	
	def handle(self, *args, **options):
		bank = TradingAccount.get(User.objects.get(id=settings.PREDICTIONMARKET_BANK_UID))
		bill_ct = ContentType.objects.get_for_model(Bill)
		
		# For every bill, make a market for its next major step and close any other markets.
		for bill in Bill.objects.filter(congress=settings.CURRENT_CONGRESS):
			market_key = None 			# current market to open
			market_name = None			# name of the market to open
			market_outcomes = None 	# dict of outcome names
			market_close = { }				# markets to close, key is market id and value is the key of the winning outcome
			
			if bill.current_status in (BillStatus.introduced, BillStatus.reported):
				market_key = 0
				market_name = "Will %s pass the %s?" % (bill.display_number, bill.originating_chamber)
				market_outcomes = { 0: "No", 1: "Yes" }
				market_close = { }
			elif bill.current_status in (BillStatus.pass_over_house, BillStatus.pass_over_senate):
				market_key = 1
				market_name = "Will %s pass the %s?" % (bill.display_number, bill.opposite_chamber)
				market_outcomes = { 0: "No", 1: "Yes" }
				market_close = { 0: 1 } # originating chamber passed
			elif bill.current_status in (BillStatus.pass_back_house, BillStatus.pass_back_senate):
				market_key = 2
				market_name = "Will %s pass in identical form in the House and Senate?" % bill.display_number
				market_outcomes = { 0: "No", 1: "Yes" }
				market_close = { 0: 1, 1: 1 } # originating chamber passed, other chamber passed
			elif bill.current_status in (BillStatus.fail_originating_house, BillStatus.fail_originating_senate):
				market_close = { 0: 0 } # originating chamber failed
			elif bill.current_status in (BillStatus.fail_second_house, BillStatus.fail_second_senate):
				market_close = { 0: 1, 1: 0 } # originating chamber passed, second chamber failed
			elif bill.current_status in (BillStatus.passed_constamend, BillStatus.passed_concurrentres, BillStatus.passed_bill,
				BillStatus.override_pass_over_house, BillStatus.override_pass_over_senate, BillStatus.vetoed_pocket,
				BillStatus.vetoed_override_fail_originating_house, BillStatus.vetoed_override_fail_originating_senate,
				BillStatus.vetoed_override_fail_second_house, BillStatus.vetoed_override_fail_second_senate,
				BillStatus.enacted_signed, BillStatus.enacted_veto_override):
				market_close = { 0: 1, 1: 1 } # originating chamber passed, other chamber passed
			elif bill.current_status in (BillStatus.passed_simpleres,):
				market_close = { 0: 1 } # originating chamber passed
			else:
				# Don't know what to do in this state, so just keep whatever we had before.
				continue

			did_see_market = False
			for market in Market.objects.filter(owner_content_type=bill_ct, owner_object_id=bill.id, isopen=True):
				if int(market.owner_key) == market_key:
					did_see_market = True
				elif int(market.owner_key) in market_close:
					print "Closing market:", market
					market.close_market() # do this before the next check to make sure no trades slip in at the last moment
					if Trade.objects.filter(outcome__market=market).exclude(account=bank).count() == 0:
						print "\tDeleting market because the only trader was the bank."
						market.delete() # TODO: Leaves the bank's account balance alone, which is not really good.
					else:
						for outcome in market.outcomes.all():
							outcome.liquidate(1.0 if market_close[int(market.owner_key)] == int(outcome.owner_key) else 0.0)
				else:
					print "Don't know what to do with market:", market, market.owner_key
						
			if not did_see_market and market_key != None:
				starting_price = compute_prognosis(bill)["prediction"] / 100.0
				
				# Create the market.
				m = Market()
				m.owner_object = bill
				m.owner_key = market_key
				m.name = market_name
				m.volatility = 200.0 # large enough so that an integer number of shares can yield .01 precision in pricing
				m.save()
				ocmap = { }
				for k, v in market_outcomes.items():
					o = Outcome()
					o.market = m
					o.owner_key = k
					o.name = v
					o.save()
					ocmap[k] = o
					
				# The bank buys enough shares to make the starting price match our bill prognosis.
				# Since we have two outcomes and the yes-price is exp(q1/b) / (exp(q1/b) + exp(q2/b))
				# then....
				if starting_price < .01: starting_price = .01
				if starting_price > .99: starting_price = .99
				shares = int(round(m.volatility * log(starting_price / (1.0 - starting_price))))
				t = None
				if starting_price > .5 and shares > 0:
					t = Trade.place(bank, ocmap[1], shares, check_balance=False)
				elif starting_price < .5 and shares < 0:
					t = Trade.place(bank, ocmap[0], -shares, check_balance=False)
					
				print "Created market", m
				if t:
					print "\twith", t.shares, "of", t.outcome


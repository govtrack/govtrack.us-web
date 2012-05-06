from django.db import models, connection
from django.contrib.auth.models import User
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic

from math import exp, log

class TradingAccount(models.Model):
	"""A user account holding the user's balance (i.e. money remaining)."""
	user = models.OneToOneField(User, db_index=True, related_name="tradingaccount")
	created = models.DateTimeField(db_index=True, auto_now_add=True)
	balance = models.FloatField(default=0) # amount of money in the account
	
	def __unicode__(self):
		return unicode(self.user)
		
	@staticmethod
	def get(user, if_exists=False):
		if not if_exists:
			acct, isnew = TradingAccount.objects.get_or_create(
				user = user,
				defaults = { "balance": settings.PREDICTIONMARKET_SEED_MONEY }
				)
			return acct
		else:
			try:
				return TradingAccount.objects.get(user = user)
			except TradingAccount.DoesNotExist:
				return None
	
	def positions(self, **filters):
		"""Returns a dict from Outcomes to a dict containing shares held of each outcome,
		the principle invested, and current unrealized profit/loss (i.e. if sold now)."""
		def tuple_add(a, b):
			return (a[0]+b[0], a[1]+b[1])
		p = { }
		for trade in Trade.objects.filter(account=self, **filters).select_related("outcome", "outcome__market").order_by('created'):
			p[trade.outcome] = tuple_add(p.get(trade.outcome, (0, 0)), (trade.shares, -trade.value))
			if p[trade.outcome][0] == 0: del p[trade.outcome] # clear when we hit zero so we don't carry forward *realized* profits/losses
		p2 = { }
		for outcome in p:
			if p[outcome][0] != 0:
				p2[outcome] = {
					"shares": p[outcome][0],
					"principle": -p[outcome][1],
					"profitloss": -(outcome.market.transaction_cost({ outcome: -p[outcome][0] }) + p[outcome][1])
				}
		return p2

	def position_in_market(self, market):
		"""Returns a tuple of total number of shares held by this account in an outcome,
		the amount invested, and the current unrealized profit/loss (i.e. if sold now)."""
		positions = self.positions(outcome__market=market)
		pl = 0.0
		for holding in positions.values():
			pl += holding["profitloss"]
		return positions, pl

	def unrealized_profit_loss(self):
		total = 0.0
		for p in self.positions().values():
			total += p["profitloss"]
		return total

class Market(models.Model):
	"""A prediction market comprising two or more outcomes."""
	
	owner_content_type = models.ForeignKey(ContentType)
	owner_object_id = models.PositiveIntegerField()
	owner_object = generic.GenericForeignKey('owner_content_type', 'owner_object_id')
	owner_key = models.CharField(max_length=16)
    
	name = models.CharField(max_length=128)
	created = models.DateTimeField(db_index=True, auto_now_add=True)
	volatility = models.FloatField(default=5.0) # prediction market volatility factor
	volume = models.IntegerField(default=0) # total held shares across all outcomes
	tradecount = models.IntegerField(default=0) # total number of trades across all outcomes
	
	isopen = models.BooleanField(default=True)
	
	def __unicode__(self):
		return self.name
		
	def prices(self):
		"""Returns a dict mapping Outcome instances to floats in the range of 0.0 to 1.0
		indicating the current ('instantaneous') market price of the outcome."""
		
		# Instantaneous prices are based on the same method used by Inkling
		# Markets, i.e. Hanson's Market Maker, according to a blog post by David
		# Pennock at http://blog.oddhead.com/2006/10/30/implementing-hansons-market-maker/.
		# The price for any outcome i is:
		#
		#     exp(q_i/b)
		#     -------------------------
		#     exp(q_1/b) + exp(q_2/b) + ...
		#
		# where q_i is the number of shares outstanding for each outcome and b is the
		# market volatility.
		
		prices = dict( (outcome, None) for outcome in self.outcomes.all() )
		denominator = 0.0
		for outcome in prices:
			v = exp(outcome.volume / self.volatility)
			denominator += v
			prices[outcome] = v
		for outcome in prices:
			prices[outcome] /= denominator
		return prices
		
	def cost_function(self, shares=None, outcomes=None):
		"""Returns the cost function where shares maps Outcome instances to the number of
		outstanding shares for each outcome, or if None then the current outstanding shares
		of each outcome."""
		
		# The cost function, based on the methodology above, is:
		#
		#    b * ln( exp(q_1/b) + exp(q_2/b) + ... )
		#
		# where q_i is the number of shares outstanding for each outcome and b is the
		# market volatility.
		
		
		c = 0.0
		if not outcomes: outcomes = list(self.outcomes.all()) # let the caller cache the objects
		for outcome in outcomes:
			if shares:
				v = shares.get(outcome, 0)
			else:
				v = outcome.volume
			c += exp(v / self.volatility)
		return self.volatility * log(c)
		
	def transaction_cost(self, shares, outcomes=None):
		"""Returns the cost to buy or sell shares of outcomes, where shares is a dict from
		Outcome instances to the number of shares to buy (positive) or sell (negative)."""
		
		# The transaction cost is the cost function after the trade minus the cost function
		# before the trade.
		
		if not outcomes: outcomes = list(self.outcomes.all()) # let the caller cache the objects
		current_shares = dict((outcome, outcome.volume) for outcome in outcomes)
		next_shares = dict((outcome, outcome.volume+shares.get(outcome, 0)) for outcome in outcomes)
		return self.cost_function(next_shares, outcomes) - self.cost_function(current_shares, outcomes)
		
	def close_market(self):
		# Any fields that are used during a trade should be modified synchronously.
		cursor = connection.cursor()
		cursor.execute("LOCK TABLES %s WRITE" % Market._meta.db_table)
		try:
			self.isopen = False
			self.save()
		finally:
			cursor.execute("UNLOCK TABLES")
		
class Outcome(models.Model):
	market = models.ForeignKey(Market, related_name="outcomes")
	owner_key = models.CharField(max_length=16)
	name = models.CharField(max_length=128)
	created = models.DateTimeField(db_index=True, auto_now_add=True)
	volume = models.IntegerField(default=0) # total held shares
	tradecount = models.IntegerField(default=0) # total number of trades
	
	def __unicode__(self):
		return self.name
		
	def price(self):
		return self.market.prices()[self]
		
	def liquidate(self, price):
		"""Forces the sale of all shares at a fixed price. Does not update market or
		outcome volumes or tradecounts, since they are no longer relevant."""
		
		# This method forces everyone to sell remaining shares at a price we set.
		# The difficultly with this function is that the only way to know how many
		# shares to sell for an account is to compute the account's position, which
		# requires summing across all trades.

		cursor = connection.cursor()
		cursor.execute("LOCK TABLES %s WRITE, %s WRITE, %s WRITE, %s WRITE" % (Trade._meta.db_table, Outcome._meta.db_table, Market._meta.db_table, TradingAccount._meta.db_table))
		try:
			if self.market.isopen: raise ValueError("Market is open!")
			
			# Compute the outstanding shares for each account.
			account_positions = { }
			for trade in self.trades.all():
				account_positions[trade.account.id] = account_positions.get(trade.account.id, 0) + trade.shares
				
			for account, shares in account_positions.items():
				if shares == 0: continue
				
				account = TradingAccount.objects.get(id=account)
				
				# Record the transaction.
				trade = Trade()
				trade.account = account
				trade.outcome = self
				trade.shares = -shares
				trade.value = price*shares
				trade.liquidation = True
				trade.save()
				
				# Update the account balance.
				account.balance += price*shares
				account.save()
		finally:
			cursor.execute("UNLOCK TABLES")
		
class Trade(models.Model):
	account = models.ForeignKey(TradingAccount, related_name="trades")
	outcome = models.ForeignKey(Outcome, related_name="trades")
	created = models.DateTimeField(db_index=True, auto_now_add=True)
	shares = models.IntegerField() # shares bought (positive) or sold (negative).
	value = models.FloatField() # monetary value of the transaction
	liquidation = models.BooleanField() # if true, this is due to the liquidation of a closing market

	def purchase_price(self):
		"""Returns the average purchase price per share."""
		return abs(self.value / self.shares)
		
	@staticmethod
	def place(account, outcome, shares, check_balance=True):
		"""Places a trade on an a market buying (shares>0) or selling (shares<0)
		shares of outcome. Returns the new Trade instance."""
		
		shares = int(shares)
		if shares == 0: raise ValueException("shares must not be zero")
		
		# Trades must be synchronized because each trade affects the price of
		# future trades. We must lock every table we touch during the transaction.
		cursor = connection.cursor()
		cursor.execute("LOCK TABLES %s WRITE, %s WRITE, %s WRITE, %s WRITE" % (Trade._meta.db_table, Outcome._meta.db_table, Market._meta.db_table, TradingAccount._meta.db_table))
		try:
			outcomes = list(outcome.market.outcomes.all())
			
			# Refresh objects now that the lock is held.
			account = TradingAccount.objects.get(id=account.id)
			outcome = Outcome.objects.get(id=outcome.id)
			market = Market.objects.get(id=outcome.market.id)
			
			if not market.isopen: raise ValueError("Market is closed.")
			
			# What will this cost?
			value = outcome.market.transaction_cost({ outcome: shares }, outcomes=outcomes)
			
			if shares > 0:
				# If a buy, check that the account has enough money for this.
				if check_balance and account.balance < value:
					raise ValueError("Account does not have sufficient funds: %f needed." % value)
			else:
				# If a sale, check that the account has enough shares for this. While owning a negative amount of
				# shares doesn't hurt the cost function, it does make an outcome's volume difficult to
				# interpret (0 might mean an equal amount of buying and selling) and makes a market's
				# volume completely nonsensical.
				pos = Trade.objects.filter(account=account, outcome=outcome).aggregate(shares=models.Sum("shares"))
				if pos["shares"] == None or pos["shares"] < shares:
					raise ValueError("Account does not have sufficient shares: %d needed." % shares)
		
			# Record the transaction.
			trade = Trade()
			trade.account = account
			trade.outcome = outcome
			trade.shares = shares
			trade.value = -value
			trade.liquidation = False
			trade.save()
			
			# Update the account balance.
			account.balance -= value
			account.save()
			
			# Update the outcome and market volumes and total trades count.
			outcome.volume += shares
			outcome.tradecount += 1
			outcome.save()
			
			market.volume += shares
			market.tradecount += 1
			market.save()
		finally:
			cursor.execute("UNLOCK TABLES")
			
		return trade
		


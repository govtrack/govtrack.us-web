#;encoding=utf8
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone
from django.template.defaultfilters import truncatechars

import json, os
from datetime import timedelta

class OkITweetedSomething(Exception):
	pass

class Command(BaseCommand):
	help = 'Tweets something interesting as @GovTrack.'

	tweets_storage_fn = 'data/misc/tweets.json'
	
	def handle(self, *args, **options):
		# What have we tweeted about before? Let's not tweet
		# it again.
		self.load_previous_tweets()
		
		try:
			# Send out a tweet.
			self.tweet_something()

		except OkITweetedSomething:
			pass
		
		finally:
			# Save the updated cache of previous tweets for next time.
			self.save_previous_tweets()

	def load_previous_tweets(self):
		if not os.path.exists(self.tweets_storage_fn):
			self.previous_tweets =  { }
		else:
			self.previous_tweets =  json.loads(open(self.tweets_storage_fn).read())

	def save_previous_tweets(self):
		with open(self.tweets_storage_fn, 'w') as output:
			json.dump(self.previous_tweets, output, sort_keys=True, indent=2)

	###

	def tweet_something(self):
		# Find something interesting to tweet!
		for func in [
			self.tweet_new_signed_laws_yday,
			self.tweet_votes_yday,
			self.tweet_new_bills_yday,
			self.tweet_a_bill_action,
			]:
			func()

	###

	def post_tweet(self, key, text, url):
		if key in self.previous_tweets:
			return

		assert len(text) + 1 + 20 + 2 <= 140
		
		text = text + " " + url
		text += u" ⚡" # symbol indicates this is an automated tweet

		print(key, text.encode("utf8"))

		self.previous_tweets[key] = {
			"text": text,
			"when": timezone.now().isoformat(),
		}
		raise OkITweetedSomething()

	###

	def tweet_new_signed_laws_yday(self):
		# Because of possible data delays, don't tweet until the afternoon.
		if timezone.now().hour < 12: return

		# Tweet count of new laws enacted yesterday.
		from bill.models import Bill, BillStatus
		count = Bill.objects.filter(
			current_status_date__gte=timezone.now().date()-timedelta(days=1),
			current_status_date__lt=timezone.now().date(),
			current_status=BillStatus.enacted_signed,
		).count()
		if count == 0: return
		self.post_tweet(
			"%s:newlaws" % timezone.now().date().isoformat(),
			"%d new law%s signed by the President yesterday." % (
				count,
				"s were" if count != 1 else " was",
				),
			"https://www.govtrack.us/congress/bills/browse#current_status[]=28&sort=-current_status_date")

	def tweet_votes_yday(self):
		# Tweet count of new laws enacted yesterday.
		from vote.models import Vote
		count = Vote.objects.filter(
			created__gte=timezone.now().date()-timedelta(days=1),
			created__lt=timezone.now().date(),
		).count()
		if count == 0: return
		self.post_tweet(
			"%s:votes" % timezone.now().date().isoformat(),
			"%d vote%s held by Congress yesterday." % (
				count,
				"s were" if count != 1 else " was",
				),
			"https://www.govtrack.us/congress/votes")

	def tweet_new_bills_yday(self):
		# Because of possible data delays, don't tweet until the afternoon.
		if timezone.now().hour < 12: return

		# Tweet count of new bills introduced yesterday.
		from bill.models import Bill, BillStatus
		count = Bill.objects.filter(
			introduced_date__gte=timezone.now().date()-timedelta(days=1),
			introduced_date__lt=timezone.now().date(),
		).count()
		if count == 0: return
		self.post_tweet(
			"%s:newbills" % timezone.now().date().isoformat(),
			"%d bill%s introduced in Congress yesterday." % (
				count,
				"s were" if count != 1 else " was",
				),
			"https://www.govtrack.us/congress/bills/browse#sort=-introduced_date")

	def tweet_a_bill_action(self):
		# Tweet an interesting action on a bill.
		from bill.models import Bill, BillStatus
		from bill.status import get_bill_really_short_status_string
		bills = list(Bill.objects.filter(
			current_status_date__gte=timezone.now().date()-timedelta(days=1),
			current_status_date__lt=timezone.now().date(),
		))
		if len(bills) == 0: return

		# Choose bill with the highest proscore.
		bills.sort(key = lambda b : -b.proscore())
		for bill in bills:
			status = BillStatus.by_value(bill.current_status).xml_code
			text = get_bill_really_short_status_string(status)
			if text == "": continue
			text = text % (
				truncatechars(bill.title, 50),
				"yesterday"
			)
			self.post_tweet(
				bill.current_status_date.isoformat() + ":bill:%s:status:%s" % (bill.congressproject_id, status),
				text,
				"https://www.govtrack.us" + bill.get_absolute_url())

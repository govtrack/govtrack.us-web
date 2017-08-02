#;encoding=utf8
from django.db.models import F
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone
from django.template.defaultfilters import truncatechars

from collections import defaultdict
import json, os, sys
from datetime import timedelta

class OkITweetedSomething(Exception):
	pass

class Command(BaseCommand):
	help = 'Tweets something interesting as @GovTrack.'

	tweets_storage_fn = 'data/misc/tweets.json'
	
	def handle(self, *args, **options):
		# Construct client.
		import twitter
		self.twitter = twitter.Api(consumer_key=settings.TWITTER_OAUTH_TOKEN, consumer_secret=settings.TWITTER_OAUTH_TOKEN_SECRET,
		                  access_token_key=settings.TWITTER_ACCESS_TOKEN, access_token_secret=settings.TWITTER_ACCESS_TOKEN_SECRET)

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
		self.tweet_new_signed_laws_yday()
		self.tweet_votes_yday(True)
		self.tweet_new_bills_yday()
		self.tweet_coming_up()
		self.tweet_a_bill_action()
		self.tweet_votes_yday(False)

	###

	def post_tweet(self, key, text, url):
		if key in self.previous_tweets:
			return

		text = truncatechars(text, 140-1-23-3) + " " + url
		text += u" 🏛️" # there's a civics building emoji there indicating to followers this is an automated tweet? the emoji is two characters (plus a space before it) as Twitter sees it

		if "TEST" in os.environ:
			# Don't tweet. Just print and exit.
			print key, text
			sys.exit(1)

		tweet = self.twitter.PostUpdate(text, verify_status_length=False) # it does not do link shortening test correctly

		self.previous_tweets[key] = {
			"text": text,
			"when": timezone.now().isoformat(),
			"tweet": tweet.AsDict(),
		}

		#print(json.dumps(self.previous_tweets[key], indent=2))

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

	def tweet_votes_yday(self, if_major):
		# Tweet count of votes yesterday, by vote type if there were any major votes.
		from vote.models import Vote, VoteCategory

		votes = Vote.objects.filter(
			created__gte=timezone.now().date()-timedelta(days=1),
			created__lt=timezone.now().date(),
		)
		if votes.count() == 0: return

		has_major = len([v for v in votes if v.is_major]) > 0
		if not has_major and if_major: return

		if not has_major:
			count = votes.count()
			msg = "%d minor vote%s held by Congress yesterday." % (
                count,
                "s were" if count != 1 else " was",
                )
		else:
			counts = defaultdict(lambda : 0)
			for v in votes:
				counts[v.category] += 1
			counts = list(counts.items())
			counts.sort(key = lambda kv : (VoteCategory.by_value(kv[0]).importance, -kv[1]))
			msg = "Votes held by Congress yesterday: " + ", ".join(
				str(value) + " on " + VoteCategory.by_value(key).label
				for key, value in counts
			)

		self.post_tweet(
			"%s:votes" % timezone.now().date().isoformat(),
			msg,
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

	def tweet_coming_up(self):
        # legislation posted as coming up within the last day
		from bill.models import Bill
		dhg_bills = Bill.objects.filter(docs_house_gov_postdate__gt=timezone.now().date()-timedelta(days=1)).filter(docs_house_gov_postdate__gt=F('current_status_date'))
		sfs_bills = Bill.objects.filter(senate_floor_schedule_postdate__gt=timezone.now().date()-timedelta(days=1)).filter(senate_floor_schedule_postdate__gt=F('current_status_date'))
		coming_up = list(dhg_bills | sfs_bills)
		coming_up.sort(key = lambda b : b.docs_house_gov_postdate if (b.docs_house_gov_postdate and (not b.senate_floor_schedule_postdate or b.senate_floor_schedule_postdate < b.docs_house_gov_postdate)) else b.senate_floor_schedule_postdate)
		for bill in coming_up:
			text = "Coming up: " + bill.display_number
			if bill.sponsor and bill.sponsor.twitterid: text += " by @" + bill.sponsor.twitterid
			text += ": " + bill.title_no_number
			self.post_tweet(
				"%s:comingup:%s" % (timezone.now().date().isoformat(), bill.congressproject_id),
				text,
				"https://www.govtrack.us" + bill.get_absolute_url())

	def tweet_a_bill_action(self):
		# Tweet an interesting action on a bill.
		from bill.models import Bill, BillStatus
		from bill.status import get_bill_really_short_status_string
		bills = list(Bill.objects.filter(
			current_status_date__gte=timezone.now().date()-timedelta(days=2),
			current_status_date__lt=timezone.now().date(),
		).exclude(
			current_status=BillStatus.introduced,
		))
		if len(bills) == 0: return

		# Choose bill with the most salient status, breaking ties with the highest proscore.
		bills.sort(key = lambda b : (BillStatus.by_value(b.current_status).sort_order, b.proscore()), reverse=True)
		for bill in bills:
			status = BillStatus.by_value(bill.current_status).xml_code
			if "Providing for consideration" in bill.title: continue
			text = get_bill_really_short_status_string(status)
			if text == "": continue
			bill_number = bill.display_number
			if bill.sponsor and bill.sponsor.twitterid: bill_number += " by @" + bill.sponsor.twitterid
			text = text % (bill_number, u"y’day")
			text += " " + bill.title_no_number
			self.post_tweet(
				bill.current_status_date.isoformat() + ":bill:%s:status:%s" % (bill.congressproject_id, status),
				text,
				"https://www.govtrack.us" + bill.get_absolute_url())

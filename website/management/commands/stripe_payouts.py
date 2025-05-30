from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from decimal import Decimal
from collections import defaultdict
from datetime import datetime
import rtyaml

import stripe

class Command(BaseCommand):
  args = ''

  def handle(self, *args, **options):
    payout = stripe.Payout.list(limit=1).data[0]
    print(rtyaml.dump({
      "id": payout.id,
      "created": datetime.fromtimestamp(payout.created),
      "amount": str(Decimal(payout.amount) / 100)
    }))

    range = { "payout": payout.id }

    count = 0
    totals = defaultdict(lambda : 0)

    while True:
      page = stripe.BalanceTransaction.list(limit=100, **range)

      for bt in page.data:
        if bt["type"] == "payout": continue

        descr = bt["description"]
        if descr is None:
          descr = "GovTrack? - Description Unset"
        if "GovTrack" in descr:
          pass
        elif "Subscription" in descr:
          descr = "Substack Subscriptions"
        else:
          descr = "Other"

        totals[descr] += Decimal(bt["net"]) / 100
        count += 1

      if not page["has_more"]: break
      range["starting_after"] = page.data[-1].id

    total = sum(totals.values())
    assert total == Decimal(payout.amount) / 100

    totals = list(totals.items())
    totals.sort(key = lambda item : -item[1])
    for k, v in totals:
      print(v, "Stripe - " + k, sep="\t")

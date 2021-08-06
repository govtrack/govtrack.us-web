from django.db.models import Q
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import User
from django.http import HttpResponse

from datetime import timedelta

from website.models import UserProfile
from emailverification.utils import send_email_verification
from emailverification.models import Ping, BouncedEmail

reconfirmation_interval = timedelta(days=365) # one year
reconfirmation_timeout = timedelta(days=20)

class ConfirmEmailAction:
    user_id = None
    final_warning = False

    @property
    def email_template(self):
        if not self.final_warning:
            return "email/reconfirm_email"
        else:
            return "email/reconfirm_email_final"

    def get_response(self, request, vrec):
        user = User.objects.get(id=self.user_id)
        user.is_active = True
        user.save()

        prof = user.userprofile()
        prof.pending_email_reconfirmation = None
        prof.email_reconfirmed_at = timezone.now()
        prof.save()

        return HttpResponse("Thank you for confirming your email address and keeping your account active.")

class Command(BaseCommand):
    help = 'Sends some users emails to re-confirm they still have ownership over the address, and deactivates accounts that have timed out after a confirmation was sent.'

    def handle(self, *args, **options):
        self.send_reconfirmation_emails()
        self.deactivate_unconfirmed_accounts()

    def get_users_needing_reconfirmation(self):
        now = timezone.now()
        return User.objects\
            .filter(Q(email__endswith=".house.gov") | Q(email__endswith=".senate.gov")
                   | Q(subscription_lists__email__gt=0, last_login__lt=now-reconfirmation_interval))\
            .filter(is_active=True)\
            .filter(date_joined__lt=now-reconfirmation_interval)\
            .filter(Q(userprofile__email_reconfirmed_at=None) | Q(userprofile__email_reconfirmed_at__lt=now-reconfirmation_interval))\
            .distinct()

    def send_reconfirmation_emails(self):
        # Find users who are subject to reconfirmation and haven't yet
        # been sent a reconfirmation email.
        users = self.get_users_needing_reconfirmation()\
            .filter(userprofile__pending_email_reconfirmation=None)

        # Only take a bunch in this batch.
        users = users[0:1000]

        now = timezone.now()

        # Send emails.
        for user in users:
            prof = user.userprofile()

            # We track email opens in the Ping table. Get the most recent ping for a user, if any.
            # If it's newer than the most recent email reconfirmation time, then use it.
            # If that puts the user within the reconfirmation interval, move on.
            ping = Ping.objects.filter(user=user).exclude(pingtime=None).order_by('-pingtime').first()
            if ping and (prof.email_reconfirmed_at is None or prof.email_reconfirmed_at < ping.pingtime):
                prof.email_reconfirmed_at = ping.pingtime
                prof.save()
                if prof.email_reconfirmed_at > now-reconfirmation_interval:
                    continue

            print("WARN", user.id, user.date_joined.isoformat(), user.last_login.isoformat(),
                prof.email_reconfirmed_at.isoformat() if prof.email_reconfirmed_at else "-",
                user.email)

            axn = ConfirmEmailAction()
            axn.user_id = user.id
            send_email_verification(user.email, None, axn)

            # Mark mail as sent.
            prof.pending_email_reconfirmation = now
            prof.save()

    def deactivate_unconfirmed_accounts(self):
        # Find users who are subject to reconfirmation, have been
        # sent a reconfirmation email, and enough time has elapsed
        # without them having re-confirmed their email that we'll
        # now deactivate their account. Send a warning email to them
        # giving them one last chance to reconfirm.
        now = timezone.now()
        users = self.get_users_needing_reconfirmation()\
            .exclude(userprofile__pending_email_reconfirmation=None) \
            .filter(userprofile__pending_email_reconfirmation__lt=now-reconfirmation_timeout)
        
        # Only take a bunch in this batch.
        users = users[0:1000]

        # Send emails & deactivate.
        for user in users:
            prof = user.userprofile()
            print("DEACTIVATE", user.id, user.date_joined.isoformat(), user.last_login.isoformat(),
                prof.email_reconfirmed_at.isoformat() if prof.email_reconfirmed_at else "-",
                prof.pending_email_reconfirmation.isoformat(),
                user.email)

            # Skip if there is a BouncedEmail record for this user.
            if not BouncedEmail.objects.filter(user=user).exists():
                axn = ConfirmEmailAction()
                axn.user_id = user.id
                axn.final_warning = True
                send_email_verification(user.email, None, axn)

            # Deactivate user.
            user.is_active = False
            user.save()

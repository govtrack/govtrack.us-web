from django.db.models import Q
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import User
from django.http import HttpResponse

from datetime import timedelta

from website.models import UserProfile
from emailverification.utils import send_email_verification

reconfirmation_interval = timedelta(days=30.5*4) # four months
reconfirmation_timeout = timedelta(days=30)

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
            .filter(email__endswith=".gov")\
            .filter(is_active=True)\
            .filter(date_joined__lt=now-reconfirmation_interval)\
            .filter(Q(userprofile__email_reconfirmed_at=None) | Q(userprofile__email_reconfirmed_at__lt=now-reconfirmation_interval))

    def send_reconfirmation_emails(self):
        # Find users who are subject to reconfirmation and haven't yet
        # been sent a reconfirmation email.
        users = self.get_users_needing_reconfirmation()\
            .filter(userprofile__pending_email_reconfirmation=None)

        # Only take a bunch in this batch.
        users = users[0:100]
        
        now = timezone.now()

        # Send emails.
        for user in users:
            print("WARN", user.id, user.date_joined.isoformat(), user.last_login.isoformat(),
                user.userprofile().email_reconfirmed_at.isoformat() if user.userprofile().email_reconfirmed_at else "-",
                user.email)

            axn = ConfirmEmailAction()
            axn.user_id = user.id
            send_email_verification(user.email, None, axn)

            # Mark mail as sent.
            prof = user.userprofile()
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
        users = users[0:100]

        # Send emails.
        for user in users:
            print("DEACTIVATE", user.id, user.date_joined.isoformat(), user.last_login.isoformat(),
                user.userprofile().email_reconfirmed_at.isoformat() if user.userprofile().email_reconfirmed_at else "-",
                user.userprofile().pending_email_reconfirmation.isoformat(),
                user.email)

            axn = ConfirmEmailAction()
            axn.user_id = user.id
            axn.final_warning = True
            send_email_verification(user.email, None, axn)

            # Deactivate user.
            user.is_active = False
            user.save()
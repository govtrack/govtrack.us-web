from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

import random

from email_validator import validate_email, EmailNotValidError

class EmailBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, **kwargs):
        self.fail_silently = fail_silently
        self.backends = settings.EMAIL_BACKENDS
        self.open_backends = None

    def open(self):
        if self.open_backends is not None:
            raise Exception("Connection is already open.")
        self.open_backends = { }

    def close(self):
        if self.open_backends is None:
            return # already closed
        for backend in self.open_backends.values():
            try:
                backend.close()
            except:
                pass
        self.open_backends = None

    def send_messages(self, email_messages):
        if self.open_backends is None:
            # Run this in an open-close block.
            with self:
                self.send_messages(email_messages)
            return

        # Group the messages by backend.
        messages = { }
        for m in email_messages:
            messages \
                .setdefault(self.select_backend(m), []) \
                .append(m)

        # Now send by backend.
        for backend_key, email_messages in messages.items():
            # Get the open backend instance if it's already open.
            if backend_key in self.open_backends:
                backend = self.open_backends[backend_key]

                # Ensure SMTP backends are still truly open. Sometimes the socket gets reset.
                if hasattr(backend, 'connection'):
                    if not backend.connection:
                        raise ValueError("the mail connection should be open already")
                    if not backend.connection.sock: # socket seems to have been closed - reopen it
                        backend.connection = None
                        backend.open()

            # Otherwise, construct the backend (the backends list contains
            # functions that lazy-load the actual backend).
            else:
                backend = self.backends[backend_key](fail_silently=self.fail_silently)
                backend.open()
                self.open_backends[backend_key] = backend

            # Pre-process the message.
            preprocfuncname = "preprocess_message_for_" + backend_key
            if hasattr(self, preprocfuncname):
                f = getattr(self, preprocfuncname)
                for m in email_messages:
                    f(m)

            # Pass it the messages.
            backend.send_messages(email_messages)

    def select_backend(self, message):
        # Select a backend at random, returning a key in the self.backends dict.
        return random.choice(list(self.backends.keys()))

class GovTrackEmailBackend(EmailBackend):
    def select_backend(self, message):
        # Divert Microsoft-owned domains to backend "2" and everything else to
        # backend "1".
        for recip in message.to:
            if GovTrackEmailBackend.is_microsoft_address(recip):
                return '2'
        return '1'

    @staticmethod
    def is_microsoft_address(email):
        # Extract domain.
        try:
            domain = email.lower().split("@", 1)[1]
        except IndexError:
            # Input was invalid, no @-sign.
            return False

        # Known MS addresses, plus our own address for testing.
        if domain in ("live.com", "hotmail.com", "outlook.com", "msn.com", "govtrack.us"):
            return True

        # Of our top 25 domains, these are definitely not hosted by Microsoft.
        if domain in ("gmail.com", "yahoo.com", "aol.com", "comcast.net", "sbcglobal.net", "verizon.net", "att.net", "cox.net", "bellsouth.net", "me.com", "earthlink.net", "mac.com", "charter.net", "icloud.com", "ymail.com", "optonline.net", "juno.com", "rocketmail.com"):
            return False
        if domain.endswith(".gov") or domain.endswith(".mil"):
            return False

        # For the rest, do a MX lookup. Domains handled by *.mail.protection.outlook.com are Microsoft addresses.
        # Get the MX records, and take the first record's host component.
        try:
            mx = validate_email(email)['mx'][0][1]
        except EmailNotValidError as e:
            # Syntax or MX lookup failed?
            return False
        except (KeyError, IndexError) as e:
            # No MX info?
            return False
        if mx.endswith(".outlook.com"):
            return True
        return False

    def preprocess_message_for_2(self, msg):
        msg.body = self.fixup_mailgun_content(msg.body, msg)
        if hasattr(msg, 'alternatives'):
            for i, (content, mimetype) in enumerate(msg.alternatives):
                msg.alternatives[i] = (self.fixup_mailgun_content(content, msg), mimetype)

    def fixup_mailgun_content(self, content, msg):
        if 'X-Unsubscribe-Link' in msg.extra_headers:
            # Use a custom link we stash in the email headers.
            content = content.replace("{unsubscribe}", msg.extra_headers.get('X-Unsubscribe-Link'))
            content = content.replace("%7Bunsubscribe%7D", msg.extra_headers.get('X-Unsubscribe-Link'))
        else:
            # Fall back to Mailgun's variable.
            content = content.replace("{unsubscribe}", "%unsubscribe_url%")
            content = content.replace("%7Bunsubscribe%7D", "%unsubscribe_url%")

        content = content.replace("{accountcompany}", "Civic Impulse LLC")
        content = content.replace("{accountaddress1}", "712 H Street NE Suite 1260")
        content = content.replace("{accountcity}", "Washington")
        content = content.replace("{accountstate}", "DC")
        content = content.replace("{accountzip}", "20002")
        content = content.replace("{accountcountry}", "USA")
        return content

"""Resend HTTPS API email backend.

Outbound SMTP from Railway hangs against smtp.resend.com:587 (the request
holds the worker for the full timeout window before failing). This backend
routes every Django EmailMessage / EmailMultiAlternatives.send() call
through Resend's REST API over HTTPS instead.
"""

import logging

import httpx
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"
DEFAULT_TIMEOUT_SECONDS = 10.0


class ResendBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = getattr(settings, "RESEND_API_KEY", "") or getattr(settings, "EMAIL_HOST_PASSWORD", "")
        self.timeout = getattr(settings, "RESEND_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        if not self.api_key:
            if self.fail_silently:
                return 0
            raise RuntimeError("Resend API key not configured (set RESEND_API_KEY or EMAIL_HOST_PASSWORD).")

        sent = 0
        with httpx.Client(timeout=self.timeout) as client:
            for message in email_messages:
                try:
                    self._send_one(client, message)
                    sent += 1
                except Exception:
                    logger.exception(
                        "Resend send failed: subject=%r to=%r",
                        message.subject,
                        list(message.to),
                    )
                    if not self.fail_silently:
                        raise
        return sent

    def _send_one(self, client, message):
        payload = {
            "from": message.from_email,
            "to": list(message.to),
            "subject": message.subject,
            "text": message.body,
        }
        if message.cc:
            payload["cc"] = list(message.cc)
        if message.bcc:
            payload["bcc"] = list(message.bcc)
        if message.reply_to:
            payload["reply_to"] = list(message.reply_to)

        for content, mimetype in getattr(message, "alternatives", []) or []:
            if mimetype == "text/html":
                payload["html"] = content
                break

        response = client.post(
            RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"Resend API error {response.status_code}: {response.text[:500]}"
            )

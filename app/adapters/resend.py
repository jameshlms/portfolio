"""Resend as a MailSender, via its HTTP API (Railway's Hobby plan blocks SMTP)."""

import httpx
import structlog

from app.services.contact import OutgoingEmail
from app.services.errors import DeliveryFailed

EMAILS_URL = "https://api.resend.com/emails"
USER_AGENT = "jameshlms-portfolio/1.0"  # Resend rejects requests without one

_log = structlog.get_logger(__name__)


class ResendMailSender:
    def __init__(self, client: httpx.AsyncClient, api_key: str, sender: str) -> None:
        self._client = client
        self._api_key = api_key
        self._sender = sender

    async def send(self, email: OutgoingEmail) -> None:
        payload: dict[str, object] = {
            "from": self._sender,
            "to": [email.to],
            "subject": email.subject,
            "text": email.text,
        }
        if email.reply_to:
            payload["reply_to"] = email.reply_to

        try:
            response = await self._client.post(
                EMAILS_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "User-Agent": USER_AGENT,
                },
                timeout=10.0,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            status, body = e.response.status_code, e.response.text[:300]
            raise DeliveryFailed(f"Resend rejected the email ({status}): {body}") from e
        except httpx.HTTPError as e:
            raise DeliveryFailed(
                f"Resend could not be reached ({type(e).__name__})"
            ) from e

        _log.info("contact_email_sent", resend_id=response.json().get("id"))

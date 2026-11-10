"""What the contact form needs from outside: a bot check and a way to send mail.

Implemented by app.adapters.turnstile (HumanVerifier) and app.adapters.resend /
app.adapters.log_mail (MailSender).
"""

from typing import Protocol

from app.domain.contact import OutgoingEmail


class HumanVerifier(Protocol):
    async def verify(self, token: str, remote_ip: str | None) -> bool:
        """True if the token proves a human; raises HumanCheckUnavailable if it can't tell."""
        ...


class MailSender(Protocol):
    async def send(self, email: OutgoingEmail) -> None:
        """Deliver the email; raises DeliveryFailed if it can't."""
        ...

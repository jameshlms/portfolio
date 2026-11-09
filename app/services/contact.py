"""Contact use case: verify the visitor, then deliver their message."""

from app.domain.contact import ContactMessage, compose_email
from app.domain.errors import HumanCheckFailed
from app.ports.driven.contact import HumanVerifier, MailSender


async def send_contact_message(
    message: ContactMessage,
    *,
    token: str,
    remote_ip: str | None,
    verifier: HumanVerifier,
    sender: MailSender,
    recipient: str,
) -> None:
    """Check the visitor is human, then deliver the message to `recipient`."""
    if not await verifier.verify(token, remote_ip):
        raise HumanCheckFailed
    await sender.send(compose_email(message, recipient=recipient))

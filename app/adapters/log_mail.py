"""A MailSender for local development: logs the email instead of sending it."""

import structlog

from app.domain.contact import OutgoingEmail

_log = structlog.get_logger(__name__)


class LogMailSender:
    async def send(self, email: OutgoingEmail) -> None:
        # Metadata only: the message body is visitor input and stays out of logs.
        _log.info(
            "contact_email_not_sent",
            reason="no RESEND_API_KEY (debug mode)",
            subject=email.subject,
            has_reply_to=email.reply_to is not None,
            chars=len(email.text),
        )

"""Contact form: what a valid message is, the email it becomes, what sending one
needs from outside, and the use case that sends it.

Pure: no I/O and no framework imports. The route parses form input with
`ContactMessage.parse` and calls `send_contact_message`. Adapters implement
`HumanVerifier` (Turnstile) and `MailSender` (Resend, or a logger in
development); app.deps chooses which.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol

from app.services.errors import HumanCheckFailed, InvalidContactMessage

NAME_MAX = 100
REPLY_TO_MAX = 254
MESSAGE_MIN = 10
MESSAGE_MAX = 5000

_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_PHONE = re.compile(r"\+?[\d\s().\-]+")
_PHONE_DIGITS = range(7, 16)  # E.164 allows at most 15 digits


class Purpose(StrEnum):
    JOB = "job"
    PROJECT = "project"
    COLLABORATION = "collaboration"
    QUESTION = "question"
    OTHER = "other"

    @property
    def label(self) -> str:
        return _PURPOSE_LABELS[self]


_PURPOSE_LABELS: Mapping[Purpose, str] = MappingProxyType(
    {
        Purpose.JOB: "Job opportunity",
        Purpose.PROJECT: "Freelance or project work",
        Purpose.COLLABORATION: "Collaboration",
        Purpose.QUESTION: "Question about my work",
        Purpose.OTHER: "Something else",
    }
)


@dataclass(frozen=True)
class ContactMessage:
    name: str
    reply_to: str
    purpose: Purpose
    message: str

    @property
    def reply_email(self) -> str | None:
        """The reply address when the visitor gave an email rather than a phone number."""
        return self.reply_to if "@" in self.reply_to else None

    @classmethod
    def parse(
        cls, *, name: str, reply_to: str, purpose: str, message: str
    ) -> ContactMessage:
        """Normalise raw form input and check every rule, reporting all failures at once."""
        name = " ".join(
            name.split()
        )  # also strips newlines, which would end up in the subject
        reply_to = reply_to.strip()
        message = message.replace("\r\n", "\n").strip()
        errors: dict[str, str] = {}

        if not name:
            errors["name"] = "Enter your name."
        elif len(name) > NAME_MAX:
            errors["name"] = f"Keep your name under {NAME_MAX} characters."

        if not reply_to:
            errors["reply_to"] = "Enter an email address or phone number."
        elif len(reply_to) > REPLY_TO_MAX or not _is_email_or_phone(reply_to):
            errors["reply_to"] = "Enter a valid email address or phone number."

        if purpose not in Purpose:
            errors["purpose"] = "Choose what your message is about."

        if len(message) < MESSAGE_MIN:
            errors["message"] = f"Write at least {MESSAGE_MIN} characters."
        elif len(message) > MESSAGE_MAX:
            errors["message"] = f"Keep your message under {MESSAGE_MAX} characters."

        if errors:
            raise InvalidContactMessage(errors)
        return cls(
            name=name, reply_to=reply_to, purpose=Purpose(purpose), message=message
        )


def _is_email_or_phone(value: str) -> bool:
    if "@" in value:
        return _EMAIL.fullmatch(value) is not None
    digits = sum(c.isdigit() for c in value)
    return _PHONE.fullmatch(value) is not None and digits in _PHONE_DIGITS


@dataclass(frozen=True)
class OutgoingEmail:
    to: str
    subject: str
    text: str
    reply_to: str | None = None


def compose_email(message: ContactMessage, *, recipient: str) -> OutgoingEmail:
    """The email I receive for a contact message; replies go straight to the sender."""
    text = (
        f"Name: {message.name}\n"
        f"Reply to: {message.reply_to}\n"
        f"Purpose: {message.purpose.label}\n"
        f"\n{message.message}\n"
    )
    return OutgoingEmail(
        to=recipient,
        subject=f"[{message.purpose.label}] Message from {message.name}",
        text=text,
        reply_to=message.reply_email,
    )


# --- What sending needs from outside ---------------------------------------


class HumanVerifier(Protocol):
    async def verify(self, token: str, remote_ip: str | None) -> bool:
        """True if the token proves a human; raises HumanCheckUnavailable if it can't tell."""
        ...


class MailSender(Protocol):
    async def send(self, email: OutgoingEmail) -> None:
        """Deliver the email; raises DeliveryFailed if it can't."""
        ...


# --- Use case ------------------------------------------------------------------


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

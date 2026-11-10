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

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator
from pydantic_core import PydanticCustomError

from app.services.errors import HumanCheckFailed, InvalidContactMessage, field_errors

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


class ContactMessage(BaseModel):
    """A contact form submission that passed every rule, normalised.

    Each validator raises the message the visitor sees; `parse` turns them into
    InvalidContactMessage, keyed by field, all at once.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

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
        data = {
            "name": name,
            "reply_to": reply_to,
            "purpose": purpose,
            "message": message,
        }
        try:
            return cls.model_validate(data)
        except ValidationError as e:
            raise InvalidContactMessage(field_errors(e)) from e

    @field_validator("name", mode="before")
    @classmethod
    def _name(cls, value: str) -> str:
        name = " ".join(
            value.split()
        )  # also strips newlines, which would reach the subject
        if not name:
            raise _invalid("Enter your name.")
        if len(name) > NAME_MAX:
            raise _invalid(f"Keep your name under {NAME_MAX} characters.")
        return name

    @field_validator("reply_to", mode="before")
    @classmethod
    def _reply_to(cls, value: str) -> str:
        reply_to = value.strip()
        if not reply_to:
            raise _invalid("Enter an email address or phone number.")
        if len(reply_to) > REPLY_TO_MAX or not _is_email_or_phone(reply_to):
            raise _invalid("Enter a valid email address or phone number.")
        return reply_to

    @field_validator("purpose", mode="before")
    @classmethod
    def _purpose(cls, value: str) -> Purpose:
        if value not in Purpose:
            raise _invalid("Choose what your message is about.")
        return Purpose(value)

    @field_validator("message", mode="before")
    @classmethod
    def _message(cls, value: str) -> str:
        message = value.replace("\r\n", "\n").strip()
        if len(message) < MESSAGE_MIN:
            raise _invalid(f"Write at least {MESSAGE_MIN} characters.")
        if len(message) > MESSAGE_MAX:
            raise _invalid(f"Keep your message under {MESSAGE_MAX} characters.")
        return message


def _invalid(message: str) -> PydanticCustomError:
    """A validation error whose message is already what the visitor should read."""
    # The template must be a literal; the message travels in the error's context.
    return PydanticCustomError("contact_field", "{message}", {"message": message})


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

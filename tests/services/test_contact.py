"""Contact use case: verification and delivery, with fake ports."""

import asyncio

import pytest

from app.services.contact import ContactMessage, OutgoingEmail, send_contact_message
from app.services.errors import DeliveryFailed, HumanCheckFailed

_VALID = {
    "name": "Ada Lovelace",
    "reply_to": "ada@example.com",
    "purpose": "job",
    "message": "I'd like to talk about a role.",
}


def _parse(**overrides: str) -> ContactMessage:
    return ContactMessage.parse(**{**_VALID, **overrides})


class _Verifier:
    def __init__(self, passes: bool) -> None:
        self.passes = passes

    async def verify(self, token: str, remote_ip: str | None) -> bool:
        return self.passes


class _Sender:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[OutgoingEmail] = []

    async def send(self, email: OutgoingEmail) -> None:
        if self.fail:
            raise DeliveryFailed
        self.sent.append(email)


def _send(verifier: _Verifier, sender: _Sender) -> None:
    asyncio.run(
        send_contact_message(
            _parse(),
            token="t",
            remote_ip=None,
            verifier=verifier,
            sender=sender,
            recipient="me@example.com",
        )
    )


def test_send_delivers_once_the_visitor_is_verified() -> None:
    sender = _Sender()

    _send(_Verifier(passes=True), sender)

    assert [email.to for email in sender.sent] == ["me@example.com"]


def test_send_refuses_unverified_visitors() -> None:
    sender = _Sender()

    with pytest.raises(HumanCheckFailed):
        _send(_Verifier(passes=False), sender)
    assert sender.sent == []


def test_send_passes_delivery_failures_up() -> None:
    with pytest.raises(DeliveryFailed):
        _send(_Verifier(passes=True), _Sender(fail=True))

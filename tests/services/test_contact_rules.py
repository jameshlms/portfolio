"""Contact rules: parsing form input and composing the email. Pure."""

import pytest

from app.services.contact import MESSAGE_MAX, ContactMessage, Purpose, compose_email
from app.services.errors import InvalidContactMessage

_VALID = {
    "name": "Ada Lovelace",
    "reply_to": "ada@example.com",
    "purpose": "job",
    "message": "I'd like to talk about a role.",
}


def _parse(**overrides: str) -> ContactMessage:
    return ContactMessage.parse(**{**_VALID, **overrides})


def _errors(**overrides: str) -> dict[str, str]:
    with pytest.raises(InvalidContactMessage) as exc:
        _parse(**overrides)
    return dict(exc.value.errors)


def test_parse_normalises_input() -> None:
    message = _parse(name="  Ada \n Lovelace ", message="  Hello\r\nthere, friend  ")

    assert message.name == "Ada Lovelace"
    assert message.message == "Hello\nthere, friend"
    assert message.purpose is Purpose.JOB


@pytest.mark.parametrize(
    "reply_to", ["ada@example.com", "+44 7700 900123", "(555) 010-9999"]
)
def test_parse_accepts_email_or_phone(reply_to: str) -> None:
    assert _parse(reply_to=reply_to).reply_to == reply_to


@pytest.mark.parametrize(
    "reply_to", ["ada@", "not an address", "12345", "+1 (555) abc"]
)
def test_parse_rejects_other_reply_to(reply_to: str) -> None:
    assert "reply_to" in _errors(reply_to=reply_to)


def test_parse_reports_every_broken_rule_at_once() -> None:
    errors = _errors(name=" ", reply_to="", purpose="spam", message="short")

    assert set(errors) == {"name", "reply_to", "purpose", "message"}


def test_parse_limits_message_length() -> None:
    assert "message" in _errors(message="x" * (MESSAGE_MAX + 1))


def test_reply_email_is_only_set_for_email_addresses() -> None:
    assert _parse().reply_email == "ada@example.com"
    assert _parse(reply_to="+44 7700 900123").reply_email is None


def test_compose_email_labels_purpose_and_replies_to_sender() -> None:
    email = compose_email(_parse(), recipient="me@example.com")

    assert email.to == "me@example.com"
    assert email.reply_to == "ada@example.com"
    assert email.subject == "[Job opportunity] Message from Ada Lovelace"
    assert "Reply to: ada@example.com" in email.text
    assert email.text.endswith("I'd like to talk about a role.\n")

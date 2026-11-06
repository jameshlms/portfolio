"""The contact form through the real app, with its adapters swapped for fakes."""

import re
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.deps.contact import (
    get_contact_rate_limiter,
    get_human_verifier,
    get_mail_sender,
)
from app.deps.rate_limit import Limit, RateLimiter
from app.main import app
from app.paths import Page
from app.services.contact import (
    DeliveryFailed,
    HumanCheckUnavailable,
    OutgoingEmail,
)

_FORM = {
    "name": "Ada Lovelace",
    "reply_to": "ada@example.com",
    "purpose": "project",
    "message": "Could you help with a project?",
    "cf-turnstile-response": "token",
}
_HTMX = {"HX-Request": "true"}


class FakeVerifier:
    def __init__(self) -> None:
        self.result: bool | Exception = True

    async def verify(self, token: str, remote_ip: str | None) -> bool:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeSender:
    def __init__(self) -> None:
        self.sent: list[OutgoingEmail] = []
        self.fail = False

    async def send(self, email: OutgoingEmail) -> None:
        if self.fail:
            raise DeliveryFailed
        self.sent.append(email)


@pytest.fixture
def verifier() -> FakeVerifier:
    return FakeVerifier()


@pytest.fixture
def sender() -> FakeSender:
    return FakeSender()


@pytest.fixture
def limiter() -> RateLimiter:
    return RateLimiter(Limit(count=3, seconds=60))


@pytest.fixture
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "turnstile_site_key", "site-key")
    monkeypatch.setattr(settings, "turnstile_secret_key", "secret")
    monkeypatch.setattr(settings, "resend_api_key", "re_key")


@pytest.fixture
def client(
    enabled: None, verifier: FakeVerifier, sender: FakeSender, limiter: RateLimiter
) -> Iterator[TestClient]:
    app.dependency_overrides[get_human_verifier] = lambda: verifier
    app.dependency_overrides[get_mail_sender] = lambda: sender
    app.dependency_overrides[get_contact_rate_limiter] = lambda: limiter
    with TestClient(app, base_url="http://localhost") as c:
        yield c
    app.dependency_overrides.clear()


def test_form_shows_with_turnstile_when_enabled(client: TestClient) -> None:
    html = client.get(Page.CONTACT).text

    assert 'id="contact-form"' in html
    assert 'data-sitekey="site-key"' in html
    assert "challenges.cloudflare.com/turnstile/v0/api.js" in html


def test_form_and_its_scripts_are_hidden_until_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "turnstile_site_key", None)
    monkeypatch.setattr(settings, "turnstile_secret_key", None)
    with TestClient(app, base_url="http://localhost") as c:
        html = c.get(Page.CONTACT).text
        assert 'id="contact-form"' not in html
        assert "turnstile" not in html
        assert c.post(Page.CONTACT, data=_FORM).status_code == 404


def test_valid_message_is_sent_and_htmx_gets_the_thanks_fragment(
    client: TestClient, sender: FakeSender
) -> None:
    response = client.post(Page.CONTACT, data=_FORM, headers=_HTMX)

    assert response.status_code == 200
    assert "<html" not in response.text
    assert "Thanks, Ada Lovelace!" in response.text
    assert [email.reply_to for email in sender.sent] == ["ada@example.com"]
    assert sender.sent[0].to == settings.contact_email


def test_plain_form_post_gets_the_whole_page(client: TestClient) -> None:
    response = client.post(Page.CONTACT, data=_FORM)

    assert response.status_code == 200
    assert "<html" in response.text
    assert "Thanks, Ada Lovelace!" in response.text


def test_invalid_fields_are_reported_and_input_kept(
    client: TestClient, sender: FakeSender
) -> None:
    response = client.post(
        Page.CONTACT,
        data={**_FORM, "reply_to": "nope", "message": "short"},
        headers=_HTMX,
    )

    assert response.status_code == 422
    assert "Enter a valid email address or phone number." in response.text
    assert "Write at least 10 characters." in response.text
    assert 'value="Ada Lovelace"' in response.text
    assert re.search(r'<option value="project"\s+selected>', response.text)
    assert sender.sent == []


def test_failed_human_check_asks_to_retry(
    client: TestClient, verifier: FakeVerifier, sender: FakeSender
) -> None:
    verifier.result = False

    response = client.post(Page.CONTACT, data=_FORM, headers=_HTMX)

    assert response.status_code == 422
    assert "complete the verification check" in response.text
    assert sender.sent == []


@pytest.mark.parametrize("failure", ["verifier", "sender"])
def test_service_outage_offers_direct_email(
    client: TestClient, verifier: FakeVerifier, sender: FakeSender, failure: str
) -> None:
    if failure == "verifier":
        verifier.result = HumanCheckUnavailable()
    else:
        sender.fail = True

    response = client.post(Page.CONTACT, data=_FORM, headers=_HTMX)

    assert response.status_code == 503
    assert "be sent right now" in response.text
    assert f'href="mailto:{settings.contact_email}"' in response.text


def test_honeypot_looks_sent_but_sends_nothing(
    client: TestClient, sender: FakeSender
) -> None:
    response = client.post(
        Page.CONTACT, data={**_FORM, "website": "spam.example"}, headers=_HTMX
    )

    assert response.status_code == 200
    assert "Thanks" in response.text
    assert sender.sent == []


def test_rate_limit_blocks_repeat_posts(client: TestClient, sender: FakeSender) -> None:
    statuses = [
        client.post(Page.CONTACT, data=_FORM, headers=_HTMX).status_code
        for _ in range(4)
    ]

    assert statuses == [200, 200, 200, 429]
    assert len(sender.sent) == 3

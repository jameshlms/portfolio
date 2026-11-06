import asyncio
import json

import httpx
import pytest

from app.adapters.resend import EMAILS_URL, ResendMailSender
from app.services.contact import DeliveryFailed, OutgoingEmail

_EMAIL = OutgoingEmail(
    to="me@example.com", subject="Hi", text="Body", reply_to="ada@example.com"
)


def _send(handler: httpx.MockTransport, email: OutgoingEmail = _EMAIL) -> None:
    async def run() -> None:
        async with httpx.AsyncClient(transport=handler) as client:
            await ResendMailSender(client, "re_key", "Site <site@example.com>").send(
                email
            )

    asyncio.run(run())


def test_sends_the_documented_request() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "abc"})

    _send(httpx.MockTransport(handler))

    request = seen[0]
    assert str(request.url) == EMAILS_URL
    assert request.headers["authorization"] == "Bearer re_key"
    assert request.headers["user-agent"]
    assert json.loads(request.content) == {
        "from": "Site <site@example.com>",
        "to": ["me@example.com"],
        "subject": "Hi",
        "text": "Body",
        "reply_to": "ada@example.com",
    }


def test_omits_reply_to_when_there_is_no_email_to_reply_to() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "abc"})

    _send(
        httpx.MockTransport(handler),
        OutgoingEmail(to="me@example.com", subject="Hi", text="B"),
    )

    assert "reply_to" not in json.loads(seen[0].content)


@pytest.mark.parametrize("status", [403, 422, 429, 500])
def test_error_status_is_a_delivery_failure(status: int) -> None:
    with pytest.raises(DeliveryFailed):
        _send(
            httpx.MockTransport(
                lambda _: httpx.Response(status, json={"message": "no"})
            )
        )


def test_network_error_is_a_delivery_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    with pytest.raises(DeliveryFailed):
        _send(httpx.MockTransport(handler))

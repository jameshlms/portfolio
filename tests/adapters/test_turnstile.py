import asyncio
from urllib.parse import parse_qs

import httpx
import pytest

from app.adapters.turnstile import SITEVERIFY_URL, TurnstileVerifier
from app.services.errors import HumanCheckUnavailable


def _verify(
    handler: httpx.MockTransport, token: str = "tok", ip: str | None = "1.2.3.4"
) -> bool:
    async def run() -> bool:
        async with httpx.AsyncClient(transport=handler) as client:
            return await TurnstileVerifier(client, "secret").verify(token, ip)

    return asyncio.run(run())


def test_posts_secret_token_and_ip_and_accepts_success() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"success": True})

    assert _verify(httpx.MockTransport(handler)) is True
    assert str(seen[0].url) == SITEVERIFY_URL
    assert parse_qs(seen[0].content.decode()) == {
        "secret": ["secret"],
        "response": ["tok"],
        "remoteip": ["1.2.3.4"],
    }


def test_rejected_token_is_not_human() -> None:
    transport = httpx.MockTransport(
        lambda _: httpx.Response(
            200, json={"success": False, "error-codes": ["invalid-input-response"]}
        )
    )

    assert _verify(transport) is False


@pytest.mark.parametrize("token", ["", "x" * 2049])
def test_missing_or_oversized_token_fails_without_a_request(token: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("siteverify should not be called")

    assert _verify(httpx.MockTransport(handler), token=token) is False


@pytest.mark.parametrize(
    "response",
    [httpx.Response(500), httpx.Response(200, content=b"not json")],
)
def test_bad_siteverify_response_is_unavailable(response: httpx.Response) -> None:
    with pytest.raises(HumanCheckUnavailable):
        _verify(httpx.MockTransport(lambda _: response))


def test_network_error_is_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    with pytest.raises(HumanCheckUnavailable):
        _verify(httpx.MockTransport(handler))

"""Cloudflare Turnstile as a HumanVerifier, via the siteverify API."""

import httpx
import structlog

from app.domain.errors import HumanCheckUnavailable

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
_MAX_TOKEN_LENGTH = 2048  # documented limit; longer values can't be real tokens

_log = structlog.get_logger(__name__)


class TurnstileVerifier:
    def __init__(self, client: httpx.AsyncClient, secret: str) -> None:
        self._client = client
        self._secret = secret

    async def verify(self, token: str, remote_ip: str | None) -> bool:
        if not token or len(token) > _MAX_TOKEN_LENGTH:
            return False

        data = {"secret": self._secret, "response": token}
        if remote_ip:
            data["remoteip"] = remote_ip
        try:
            response = await self._client.post(SITEVERIFY_URL, data=data, timeout=10.0)
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError) as e:
            raise HumanCheckUnavailable("Turnstile siteverify request failed") from e

        if result.get("success") is True:
            return True
        _log.info("turnstile_rejected", error_codes=result.get("error-codes", []))
        return False

"""Wiring for the contact form: builds its adapters from settings.

Each dependency 404s when its part isn't configured, so the form's POST route
only exists where the form is switched on. Tests override these.
"""

from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, Request

from app.adapters.log_mail import LogMailSender
from app.adapters.resend import ResendMailSender
from app.adapters.turnstile import TurnstileVerifier
from app.config import settings
from app.deps.rate_limit import Limit, RateLimiter
from app.services.contact import HumanVerifier, MailSender

_CONTACT_LIMITER = RateLimiter(
    Limit(count=5, seconds=10 * 60), Limit(count=20, seconds=24 * 60 * 60)
)


def _http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


HttpClient = Annotated[httpx.AsyncClient, Depends(_http_client)]


def get_human_verifier(client: HttpClient) -> HumanVerifier:
    if not settings.turnstile_secret_key:
        raise HTTPException(status_code=404)
    return TurnstileVerifier(client, settings.turnstile_secret_key)


def get_mail_sender(client: HttpClient) -> MailSender:
    if settings.resend_api_key:
        return ResendMailSender(
            client, settings.resend_api_key, settings.contact_from_email
        )
    if settings.debug:
        return LogMailSender()
    raise HTTPException(status_code=404)


def get_contact_rate_limiter() -> RateLimiter:
    return _CONTACT_LIMITER


ContactVerifier = Annotated[HumanVerifier, Depends(get_human_verifier)]
ContactSender = Annotated[MailSender, Depends(get_mail_sender)]
ContactRateLimiter = Annotated[RateLimiter, Depends(get_contact_rate_limiter)]

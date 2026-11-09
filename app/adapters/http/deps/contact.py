"""The contact form's ports, taken from the Container.

The POST route depends on the verifier and sender, which 404 when the container
has none, so the form's endpoint only exists where the form can work.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app.adapters.http.deps.container import AppContainer
from app.adapters.http.deps.rate_limit import Limit, RateLimiter
from app.config import settings
from app.ports.driven.contact import HumanVerifier, MailSender

CONTACT_LIMITS = (
    Limit(count=5, seconds=10 * 60),
    Limit(count=20, seconds=24 * 60 * 60),
)


def get_human_verifier(container: AppContainer) -> HumanVerifier:
    if container.human_verifier is None:
        raise HTTPException(status_code=404)
    return container.human_verifier


def get_mail_sender(container: AppContainer) -> MailSender:
    if container.mail_sender is None:
        raise HTTPException(status_code=404)
    return container.mail_sender


def get_contact_rate_limiter(request: Request) -> RateLimiter:
    return request.app.state.contact_limiter


def get_turnstile_site_key(container: AppContainer) -> str | None:
    """The widget's site key when the form works end to end; None hides the form."""
    return settings.turnstile_site_key if container.can_send_contact_messages else None


ContactVerifier = Annotated[HumanVerifier, Depends(get_human_verifier)]
ContactSender = Annotated[MailSender, Depends(get_mail_sender)]
ContactRateLimiter = Annotated[RateLimiter, Depends(get_contact_rate_limiter)]
TurnstileSiteKey = Annotated[str | None, Depends(get_turnstile_site_key)]

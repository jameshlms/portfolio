"""Contact page and form submission.

GET renders the page; POST validates, checks for bots, rate limits and sends.
POST answers htmx with just the form (or its success message) and plain form
posts with the whole page, so the form works with or without htmx.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, Response

from app.config import settings
from app.deps import IsHtmx
from app.deps.contact import ContactRateLimiter, ContactSender, ContactVerifier
from app.paths import Page
from app.services import seo
from app.services.contact import ContactMessage, Purpose, send_contact_message
from app.services.errors import (
    DeliveryFailed,
    HumanCheckFailed,
    HumanCheckUnavailable,
    InvalidContactMessage,
)
from app.templates import make_templates

_templates = make_templates()
_log = structlog.get_logger(__name__)

router = APIRouter(default_response_class=HTMLResponse)

_EMPTY: Mapping[str, str] = MappingProxyType({})


@dataclass(frozen=True)
class ContactFormView:
    """Everything the form template needs to render one state of the form."""

    values: Mapping[str, str] = field(default_factory=lambda: _EMPTY)
    errors: Mapping[str, str] = field(default_factory=lambda: _EMPTY)
    form_error: str | None = None
    sent_to: str | None = None  # the sender's name once their message has gone


def _form_context(form: ContactFormView) -> dict[str, Any]:
    return {
        "form": form,
        "purposes": tuple(Purpose),
        "turnstile_site_key": settings.turnstile_site_key
        if settings.contact_form_enabled
        else None,
        "contact_email": settings.contact_email,
    }


def _render(
    request: Request,
    form: ContactFormView,
    *,
    htmx: bool = False,
    status_code: int = 200,
) -> Response:
    if htmx:
        return _templates.TemplateResponse(
            request,
            "fragments/_contact_form.html",
            _form_context(form),
            status_code=status_code,
        )
    return _templates.TemplateResponse(
        request,
        "pages/contact.html",
        {
            "seo": seo.for_page(Page.CONTACT),
            "linkedin_url": settings.linkedin_url,
            "github_url": settings.github_url,
            "gravatar_url": settings.gravatar_url,
            **_form_context(form),
        },
        status_code=status_code,
    )


@router.get(Page.CONTACT)
async def contact(request: Request) -> Response:
    return _render(request, ContactFormView())


@router.post(Page.CONTACT)
async def send_contact(
    request: Request,
    htmx: IsHtmx,
    verifier: ContactVerifier,
    sender: ContactSender,
    limiter: ContactRateLimiter,
    name: Annotated[str, Form()] = "",
    reply_to: Annotated[str, Form()] = "",
    purpose: Annotated[str, Form()] = "",
    message: Annotated[str, Form()] = "",
    website: Annotated[
        str, Form()
    ] = "",  # honeypot: hidden from people, filled by bots
    token: Annotated[str, Form(alias="cf-turnstile-response")] = "",
) -> Response:
    values = {
        "name": name,
        "reply_to": reply_to,
        "purpose": purpose,
        "message": message,
    }
    remote_ip = request.client.host if request.client else None

    if not limiter.hit(remote_ip or "unknown"):
        form = ContactFormView(
            values=values,
            form_error="Too many messages from your connection. Please try again later, "
            "or email me directly.",
        )
        return _render(request, form, htmx=htmx, status_code=429)

    if website:
        _log.info("contact_honeypot_filled")
        return _render(
            request, ContactFormView(sent_to=" ".join(name.split())), htmx=htmx
        )

    try:
        parsed = ContactMessage.parse(**values)
        await send_contact_message(
            parsed,
            token=token,
            remote_ip=remote_ip,
            verifier=verifier,
            sender=sender,
            recipient=settings.contact_email,
        )
    except InvalidContactMessage as e:
        form = ContactFormView(values=values, errors=e.errors)
        return _render(request, form, htmx=htmx, status_code=422)
    except HumanCheckFailed:
        form = ContactFormView(
            values=values,
            form_error="Please complete the verification check and try again.",
        )
        return _render(request, form, htmx=htmx, status_code=422)
    except (HumanCheckUnavailable, DeliveryFailed):
        _log.exception("contact_send_failed")
        form = ContactFormView(
            values=values,
            form_error="Sorry, your message couldn't be sent right now. Please try again "
            "later, or email me directly.",
        )
        return _render(request, form, htmx=htmx, status_code=503)

    return _render(request, ContactFormView(sent_to=parsed.name), htmx=htmx)

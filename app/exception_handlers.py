"""Every error the website can raise, turned into a response.

- DomainError: mapped to a status by type (`_DOMAIN_STATUS`, most specific class
  wins). An unmapped domain error is a bug: 500, logged.
- HTTPException: its own status.
- RequestValidationError (bad query or form input FastAPI rejects): 422.
- Any other exception: 500. Starlette re-raises it after responding, so the
  server logs the traceback; it isn't logged here as well.

Paths under /api/ get JSON. Pages get errors/error.html; htmx requests get
fragments/_error.html, retargeted at the page's <main> (htmx 4 swaps error
responses by default, which would otherwise nest a page inside the small element
that made the request).
"""

from collections.abc import Callable, Coroutine, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import structlog
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException

from app.deps.htmx import wants_fragment
from app.services import seo
from app.services.errors import (
    DeliveryFailed,
    DomainError,
    HumanCheckFailed,
    HumanCheckUnavailable,
    InvalidContactMessage,
    PostNotFound,
    PostsUnavailable,
    UnknownTag,
)
from app.templates import make_templates

_templates = make_templates()
_log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ErrorPage:
    title: str
    message: str


_PAGES: Mapping[int, ErrorPage] = MappingProxyType(
    {
        404: ErrorPage("Page not found", "That page doesn't exist."),
        422: ErrorPage("Invalid request", "Something in that request wasn't valid."),
        503: ErrorPage(
            "Temporarily unavailable",
            "This part of the site can't load right now. Please try again shortly.",
        ),
        500: ErrorPage("Something went wrong", "Something went wrong on my end."),
    }
)

# What each domain error means over HTTP. Errors that never reach a request (the
# sync CLI's InvalidPost / InvalidPosts) and the feature bases stay unmapped, so
# one surfacing here shows up as a 500 and a log line. A test checks every
# domain error is either here or listed as CLI-only.
_DOMAIN_STATUS: Mapping[type[DomainError], int] = MappingProxyType(
    {
        PostNotFound: 404,
        UnknownTag: 404,
        PostsUnavailable: 503,
        InvalidContactMessage: 422,
        HumanCheckFailed: 422,
        HumanCheckUnavailable: 503,
        DeliveryFailed: 503,
    }
)


def status_for(error: DomainError) -> int | None:
    """The status for `error`'s most specific mapped class, or None if unmapped."""
    for cls in type(error).__mro__:
        if cls in _DOMAIN_STATUS:
            return _DOMAIN_STATUS[cls]
    return None


def _error_response(request: Request, status_code: int, detail: Any) -> Response:
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": detail}, status_code=status_code)

    error = _PAGES.get(status_code, _PAGES[500])
    htmx = wants_fragment(request.headers)
    context = {
        "seo": seo.for_error_page(error.title, error.message, request.url.path),
        "error": error,
        "status_code": status_code,
        "htmx": htmx,
    }
    if htmx:
        return _templates.TemplateResponse(
            request,
            "fragments/_error.html",
            context,
            status_code=status_code,
            headers={"HX-Retarget": "#main-content", "HX-Reswap": "outerHTML"},
        )
    return _templates.TemplateResponse(
        request, "errors/error.html", context, status_code=status_code
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> Response:
    return _error_response(request, exc.status_code, exc.detail)


async def domain_error_handler(request: Request, exc: DomainError) -> Response:
    status_code = status_for(exc)
    if status_code is None:
        _log.error("unmapped_domain_error", error=type(exc).__name__, exc_info=exc)
        return _error_response(request, 500, "Internal Server Error")
    if status_code >= 500:
        _log.warning("dependency_unavailable", error=type(exc).__name__, exc_info=exc)
    return _error_response(request, status_code, str(exc) or type(exc).__name__)


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> Response:
    return _error_response(request, 422, exc.errors())


async def unexpected_error_handler(request: Request, exc: Exception) -> Response:
    return _error_response(request, 500, "Internal Server Error")


type ExceptionHandler = Callable[[Request, Any], Coroutine[Any, Any, Response]]

# Annotated with FastAPI's parameter type: dict is invariant, so the inferred
# dict[type[HTTPException], ...] wouldn't be accepted.
exception_handlers: dict[int | type[Exception], ExceptionHandler] = {
    HTTPException: http_exception_handler,
    DomainError: domain_error_handler,
    RequestValidationError: validation_error_handler,
    Exception: unexpected_error_handler,
}

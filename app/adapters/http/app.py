"""The website as a driving adapter: `create_app(container)` builds the FastAPI app.

Everything request-facing lives in this package; the ports it serves come from
the Container, so the app never constructs an adapter itself.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.adapters.http import HTTP_DIR
from app.adapters.http.deps.contact import CONTACT_LIMITS
from app.adapters.http.deps.rate_limit import RateLimiter
from app.adapters.http.exception_handlers import exception_handlers
from app.adapters.http.middleware import middleware
from app.adapters.http.paths import Internal
from app.adapters.http.routes import blog, contact, health, pages, seo
from app.config import settings
from app.container import Container

_log = structlog.get_logger(__name__)


def create_app(
    container: Container, *, contact_limiter: RateLimiter | None = None
) -> FastAPI:
    """The website, serving `container`'s ports. The container is closed at shutdown."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        _log.info("application_startup")
        yield
        await container.close()
        _log.info("application_shutdown")

    app = FastAPI(
        debug=settings.debug,
        middleware=middleware,
        exception_handlers=exception_handlers,
        lifespan=lifespan,
    )
    app.state.container = container
    # Per app, so each test's app starts with a clean count.
    app.state.contact_limiter = contact_limiter or RateLimiter(*CONTACT_LIMITS)

    app.mount(
        Internal.STATIC, StaticFiles(directory=HTTP_DIR / "static"), name="static"
    )
    # The projects router is registered once its pages are built.
    for router in (health, pages, blog, contact, seo):
        app.include_router(router.router)
    return app

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import structlog
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import close_engine
from app.exception_handlers import exception_handlers
from app.log_config import configure_logging
from app.middleware import middleware
from app.routes import blog, contact, health, pages, seo

_app_dir = Path(__file__).parent


configure_logging()


logger: structlog.BoundLogger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Application startup")
    # One pooled client for outbound API calls (Turnstile, Resend).
    app.state.http_client = httpx.AsyncClient()
    yield
    await app.state.http_client.aclose()
    await close_engine()
    logger.info("Application shutdown")


app = FastAPI(
    debug=settings.debug,
    middleware=middleware,
    exception_handlers=exception_handlers,
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=_app_dir / "static"), name="static")

# The projects router is registered once its pages are built.
app.include_router(health.router)
app.include_router(pages.router)
app.include_router(blog.router)
app.include_router(contact.router)
app.include_router(seo.router)

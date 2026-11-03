from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import close_engine
from app.exception_handlers import exception_handlers
from app.middleware import middleware
from app.routes import health, pages, seo

_app_dir = Path(__file__).parent


structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=False,
)


logger: structlog.BoundLogger = structlog.get_logger()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Application startup")
    yield
    await close_engine()
    logger.info("Application shutdown")


app = FastAPI(
    debug=settings.debug,
    middleware=middleware,
    exception_handlers=exception_handlers,
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=_app_dir / "static"), name="static")

# blog and projects routers are registered once their pages are built.
app.include_router(health.router)
app.include_router(pages.router)
app.include_router(seo.router)

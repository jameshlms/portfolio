"""structlog setup, shared by the web app and the CLI. Called once, at each entry point."""

import logging
import sys

import structlog

from app.config import settings


def configure_logging() -> None:
    renderer: structlog.typing.Processor = (
        structlog.dev.ConsoleRenderer()
        if settings.debug
        else structlog.processors.JSONRenderer()
    )
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            renderer,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )
    # Uvicorn sets up stdlib logging for the web app; the CLI has no one else to.
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)

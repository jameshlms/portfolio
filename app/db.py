from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from functools import cache
from typing import Any, ClassVar

from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    # Every datetime column is timestamptz: values are aware and stored as UTC.
    type_annotation_map: ClassVar[dict[Any, Any]] = {datetime: DateTime(timezone=True)}


# Built on first use, not at import, so the app boots without DATABASE_URL until a
# route actually needs the database.
@cache
def get_engine() -> AsyncEngine:
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL is not set.")
    return create_async_engine(settings.database_url, pool_pre_ping=True)


@cache
def _session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with _session_factory()() as session:
        yield session


@asynccontextmanager
async def transaction() -> AsyncIterator[AsyncSession]:
    """A session in one transaction: committed on exit, rolled back on error."""
    async with _session_factory().begin() as session:
        yield session


async def close_engine() -> None:
    if get_engine.cache_info().currsize:
        await get_engine().dispose()

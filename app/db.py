from collections.abc import AsyncGenerator
from functools import cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


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


async def close_engine() -> None:
    if get_engine.cache_info().currsize:
        await get_engine().dispose()

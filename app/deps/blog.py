"""Wiring for the blog: which PostRepository a request reads from.

With DATABASE_URL set, posts come from Postgres through a per-request session.
Without it, the blog is empty instead of failing, so the app (and its sitemap)
still runs locally with no database. Tests override `get_post_repository`.
"""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends

from app.adapters.memory_posts import InMemoryPostRepository
from app.adapters.sql_posts import SqlPostRepository
from app.config import settings
from app.db import get_session
from app.services.blog import PostRepository


async def get_post_repository() -> AsyncIterator[PostRepository]:
    if settings.database_url is None:
        yield InMemoryPostRepository()
        return
    async for session in get_session():
        yield SqlPostRepository(session)


Posts = Annotated[PostRepository, Depends(get_post_repository)]

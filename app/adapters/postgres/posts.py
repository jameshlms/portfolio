"""PostRepository over the blog_posts table (Postgres, async SQLAlchemy).

`sql_post_repositories` is the PostRepositoryScope bootstrap hands out: each
scope is one session in one transaction, committed when the block exits
cleanly. Requests get a scope each; the sync CLI runs `replace_all` in one, so
a failed sync leaves the previous posts in place.

Database and connection failures leave this module as PostsUnavailable, the
port's error, never as SQLAlchemy, asyncpg or socket errors.
"""

import functools
from collections.abc import AsyncIterator, Callable, Coroutine, Sequence
from contextlib import asynccontextmanager
from datetime import datetime
from types import CoroutineType
from typing import Any

from sqlalchemy import ColumnElement, delete, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql import func

from app.adapters.postgres.models import BlogPost
from app.domain.blog import Post, PostSummary, RenderedPost
from app.domain.errors import PostsUnavailable
from app.ports.driven.blog import PostRepository, PostRepositoryScope

# Columns sync writes; a row is only rewritten (and updated_at bumped) when one differs.
_SYNCED = (
    "has_charts",
    "title",
    "summary",
    "tags",
    "published_at",
    "revised_at",
    "content",
    "content_html",
)


def _is_live(as_of: datetime) -> ColumnElement[bool]:
    return BlogPost.published_at.is_not(None) & (BlogPost.published_at <= as_of)


# SQLAlchemy wraps driver errors; connection failures (refused, DNS, timeouts)
# arrive from asyncpg as OSError subclasses.
_STORAGE_ERRORS = (SQLAlchemyError, OSError)


def _translated[**P, R](
    method: Callable[P, Coroutine[Any, Any, R]],
) -> Callable[P, CoroutineType[Any, Any, R]]:
    """Re-raise storage failures from `method` as PostsUnavailable.

    Returns CoroutineType, what `async def` produces, so decorated methods still
    match the PostRepository protocol's `async def` signatures.
    """

    @functools.wraps(method)
    async def translated(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await method(*args, **kwargs)
        except _STORAGE_ERRORS as e:
            raise PostsUnavailable("The posts database can't be reached.") from e

    return translated


def sql_post_repositories(
    sessions: async_sessionmaker[AsyncSession],
) -> PostRepositoryScope:
    @asynccontextmanager
    async def scope() -> AsyncIterator[PostRepository]:
        # Only the commit is translated here: the repository translates its own
        # queries, and anything else raised in the block passes through as is.
        # If the block raises, the commit is skipped and closing rolls back.
        async with sessions() as session:
            yield SqlPostRepository(session)
            await _translated(session.commit)()

    return scope


class SqlPostRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @_translated
    async def published(self, as_of: datetime) -> tuple[PostSummary, ...]:
        rows = await self._session.execute(
            select(
                BlogPost.slug,
                BlogPost.title,
                BlogPost.summary,
                BlogPost.tags,
                BlogPost.published_at,
                BlogPost.revised_at,
            )
            .where(_is_live(as_of))
            .order_by(BlogPost.published_at.desc())
        )
        return tuple(
            PostSummary(
                slug=slug,
                title=title,
                summary=summary,
                tags=tuple(tags),
                published_at=published_at,
                revised_at=revised_at,
            )
            for slug, title, summary, tags, published_at, revised_at in rows
        )

    @_translated
    async def get_published(self, slug: str, as_of: datetime) -> Post | None:
        row = await self._session.scalar(
            select(BlogPost).where(BlogPost.slug == slug, _is_live(as_of))
        )
        if row is None or row.published_at is None:
            return None
        return Post(
            slug=row.slug,
            title=row.title,
            summary=row.summary,
            tags=tuple(row.tags),
            published_at=row.published_at,
            revised_at=row.revised_at,
            html=row.content_html,
            has_charts=row.has_charts,
        )

    @_translated
    async def replace_all(self, posts: Sequence[RenderedPost]) -> tuple[str, ...]:
        if posts:
            stmt = insert(BlogPost).values([_row(p) for p in posts])
            current = tuple_(*(getattr(BlogPost, c) for c in _SYNCED))
            incoming = tuple_(*(getattr(stmt.excluded, c) for c in _SYNCED))
            await self._session.execute(
                stmt.on_conflict_do_update(
                    index_elements=[BlogPost.slug],
                    set_={
                        **{c: getattr(stmt.excluded, c) for c in _SYNCED},
                        # Set explicitly: ORM onupdate doesn't apply to ON CONFLICT.
                        "updated_at": func.now(),
                    },
                    where=current.is_distinct_from(incoming),
                )
            )
        removed = await self._session.scalars(
            delete(BlogPost)
            .where(BlogPost.slug.not_in([p.source.slug for p in posts]))
            .returning(BlogPost.slug)
        )
        return tuple(sorted(removed))


def _row(post: RenderedPost) -> dict[str, object]:
    s = post.source
    return {
        "slug": s.slug,
        "title": s.title,
        "summary": s.summary,
        "tags": list(s.tags),
        "published_at": s.published_at,
        "revised_at": s.revised_at,
        "content": s.markdown,
        "content_html": post.html,
        "has_charts": post.has_charts,
    }

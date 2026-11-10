"""PostRepository over the blog_posts table (Postgres, async SQLAlchemy).

The caller owns the session and its transaction: requests use a session per
request, and the sync CLI runs `replace_all` in one transaction, so a failed
sync leaves the previous posts in place.

Database and connection failures leave this module as PostsUnavailable, never
as SQLAlchemy, asyncpg or socket errors.
"""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime

from sqlalchemy import ColumnElement, delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BlogPost
from app.services.blog import Post, PostSummary, RenderedPost
from app.services.errors import PostsUnavailable


@contextmanager
def storage_errors() -> Iterator[None]:
    """Re-raise database failures as PostsUnavailable.

    SQLAlchemy wraps driver errors; connection failures (refused, DNS, timeouts)
    arrive from asyncpg as plain OSError.
    """
    try:
        yield
    except (SQLAlchemyError, OSError) as e:
        raise PostsUnavailable("The posts database can't be reached.") from e


def _is_live(as_of: datetime) -> ColumnElement[bool]:
    return BlogPost.published_at.is_not(None) & (BlogPost.published_at <= as_of)


class SqlPostRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def published(self, as_of: datetime) -> tuple[PostSummary, ...]:
        with storage_errors():
            rows = await self._session.scalars(
                select(BlogPost)
                .where(_is_live(as_of))
                .order_by(BlogPost.published_at.desc())
            )
            return tuple(_summary(row) for row in rows)

    async def get_published(self, slug: str, as_of: datetime) -> Post | None:
        with storage_errors():
            row = await self._session.scalar(
                select(BlogPost).where(BlogPost.slug == slug, _is_live(as_of))
            )
        return _post(row) if row else None

    async def replace_all(self, posts: Sequence[RenderedPost]) -> tuple[str, ...]:
        # The Markdown files are the source of truth, so a sync rewrites the table.
        with storage_errors():
            existing = set(await self._session.scalars(select(BlogPost.slug)))
            await self._session.execute(delete(BlogPost))
            self._session.add_all(_row(post) for post in posts)
            await self._session.flush()
        return tuple(sorted(existing - {post.source.slug for post in posts}))


def _summary(row: BlogPost) -> PostSummary:
    assert row.published_at is not None  # only live rows are read back
    return PostSummary(
        slug=row.slug,
        title=row.title,
        summary=row.summary,
        tags=tuple(row.tags),
        published_at=row.published_at,
        revised_at=row.revised_at,
    )


def _post(row: BlogPost) -> Post:
    return Post(
        **asdict(_summary(row)), html=row.content_html, has_charts=row.has_charts
    )


def _row(post: RenderedPost) -> BlogPost:
    s = post.source
    return BlogPost(
        slug=s.slug,
        title=s.title,
        summary=s.summary,
        tags=list(s.tags),
        published_at=s.published_at,
        revised_at=s.revised_at,
        content=s.markdown,
        content_html=post.html,
        has_charts=post.has_charts,
    )

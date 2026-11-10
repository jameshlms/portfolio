"""PostRepository contract, run against every implementation.

The Postgres cases need a migrated database: set TEST_DATABASE_URL (CI does,
after `alembic upgrade head`). Each test runs in a transaction that is rolled back.
"""

import os
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import timedelta

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.adapters.memory_posts import InMemoryPostRepository
from app.adapters.sql_posts import SqlPostRepository
from app.db import Base
from app.models import BlogPost
from app.ports.driven.blog import PostRepository
from tests.blog_factories import NOW, PUBLISHED, rendered

pytestmark = pytest.mark.anyio

_DB_URL = os.environ.get("TEST_DATABASE_URL", "").replace(
    "postgresql://", "postgresql+asyncpg://"
)
needs_db = pytest.mark.skipif(not _DB_URL, reason="TEST_DATABASE_URL is not set")


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession | None]:
    """A session in a transaction that's rolled back; None without a database."""
    if not _DB_URL:
        yield None
        return
    engine = create_async_engine(_DB_URL)
    async with engine.connect() as conn:
        transaction = await conn.begin()
        yield AsyncSession(bind=conn, expire_on_commit=False)
        await transaction.rollback()
    await engine.dispose()


# Depends on `session` directly: anyio can't start an async fixture from
# request.getfixturevalue() while the test's event loop is running.
@pytest.fixture(params=["memory", pytest.param("sql", marks=needs_db)])
def repository(
    request: pytest.FixtureRequest, session: AsyncSession | None
) -> PostRepository:
    if request.param == "memory":
        return InMemoryPostRepository()
    assert session is not None
    return SqlPostRepository(session)


# --- Contract ------------------------------------------------------------------


async def test_published_lists_live_posts_newest_first(
    repository: PostRepository,
) -> None:
    await repository.replace_all(
        [
            rendered("older"),
            rendered("newer", published_at=PUBLISHED + timedelta(days=1)),
            rendered("draft", published_at=None),
            rendered("scheduled", published_at=NOW + timedelta(minutes=1)),
        ]
    )

    posts = await repository.published(NOW)

    assert [p.slug for p in posts] == ["newer", "older"]


async def test_get_published_returns_the_whole_post(repository: PostRepository) -> None:
    post = replace(rendered("a", tags=("python", "sql")), has_charts=True)
    await repository.replace_all([post, rendered("plain")])

    found = await repository.get_published("a", NOW)
    plain = await repository.get_published("plain", NOW)

    assert found is not None
    assert (found.title, found.tags, found.published_at, found.html) == (
        post.source.title,
        ("python", "sql"),
        PUBLISHED,
        post.html,
    )
    assert found.has_charts is True
    assert plain is not None and plain.has_charts is False


@pytest.mark.parametrize("slug", ["missing", "draft", "scheduled"])
async def test_get_published_hides_unpublished_posts(
    repository: PostRepository, slug: str
) -> None:
    await repository.replace_all(
        [
            rendered("draft", published_at=None),
            rendered("scheduled", published_at=NOW + timedelta(days=1)),
        ]
    )

    assert await repository.get_published(slug, NOW) is None


async def test_replace_all_updates_adds_and_removes(repository: PostRepository) -> None:
    await repository.replace_all([rendered("kept"), rendered("gone")])

    removed = await repository.replace_all(
        [rendered("kept", title="New title"), rendered("added")]
    )

    assert removed == ("gone",)
    titles = {p.slug: p.title for p in await repository.published(NOW)}
    assert titles == {"kept": "New title", "added": "Title of added"}


async def test_replace_all_with_nothing_removes_everything(
    repository: PostRepository,
) -> None:
    await repository.replace_all([rendered("a"), rendered("b")])

    assert await repository.replace_all([]) == ("a", "b")
    assert await repository.published(NOW) == ()


# --- Postgres only -------------------------------------------------------------


@needs_db
async def test_unchanged_posts_are_not_rewritten(session: AsyncSession) -> None:
    repository = SqlPostRepository(session)
    await repository.replace_all([rendered("same"), rendered("edited")])
    await session.execute(text("UPDATE blog_posts SET updated_at = '2000-01-01'"))

    await repository.replace_all(
        [rendered("same"), replace(rendered("edited"), html="<p>new</p>")]
    )

    # .all(), not .tuples(): a Result has keys(), so dict() would treat it as a mapping.
    result = await session.execute(select(BlogPost.slug, BlogPost.updated_at))
    rows = {slug: updated_at for slug, updated_at in result.all()}
    assert rows["same"].year == 2000
    assert rows["edited"].year > 2000


@needs_db
async def test_trigger_indexes_posts_for_search(session: AsyncSession) -> None:
    await SqlPostRepository(session).replace_all(
        [rendered("a", markdown="Partitioning large tables")]
    )

    match = await session.scalar(
        select(BlogPost.slug).where(
            BlogPost.search_vector.op("@@")(text("to_tsquery('english', 'partition')"))
        )
    )
    assert match == "a"


@needs_db
async def test_migrations_match_the_models(session: AsyncSession) -> None:
    conn = await session.connection()

    diff = await conn.run_sync(
        lambda sync_conn: compare_metadata(
            MigrationContext.configure(sync_conn), Base.metadata
        )
    )

    assert diff == []

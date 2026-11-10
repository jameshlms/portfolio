"""The CLI's checks that run before it touches the database."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from app.adapters.cli import commands as cli
from app.adapters.markdown import MarkdownItRenderer
from app.adapters.memory_posts import InMemoryPostRepository, memory_post_repositories
from app.container import Container
from app.domain.errors import PostsUnavailable
from app.ports.driven.blog import PostRepository
from tests.blog_factories import CLOCK


@asynccontextmanager
async def _fail_if_opened() -> AsyncIterator[PostRepository]:
    raise AssertionError("the database must not be touched")
    yield  # pragma: no cover  (makes this an async generator)


_CONTAINER = Container(
    posts=_fail_if_opened, renderer=MarkdownItRenderer(), clock=CLOCK
)


def test_invalid_post_aborts_without_writing(tmp_path: Path) -> None:
    (tmp_path / "bad.md").write_text("---\ntitle: No summary\n---\nBody")

    assert cli.main(["sync-posts", "--dir", str(tmp_path)], _CONTAINER) == 1


def test_post_with_a_missing_chart_aborts_without_writing(tmp_path: Path) -> None:
    (tmp_path / "charted.md").write_text(
        "---\ntitle: T\nsummary: S\n---\n```plotly\nmissing.json\n```\n"
    )

    assert cli.main(["sync-posts", "--dir", str(tmp_path)], _CONTAINER) == 1


def test_missing_directory_fails(tmp_path: Path) -> None:

    assert cli.main(["sync-posts", "--dir", str(tmp_path / "nope")], _CONTAINER) == 1


def test_valid_posts_need_durable_storage(tmp_path: Path) -> None:
    (tmp_path / "ok.md").write_text("---\ntitle: T\nsummary: S\n---\nBody")

    assert cli.main(["sync-posts", "--dir", str(tmp_path)], _CONTAINER) == 1


def test_valid_posts_are_stored(tmp_path: Path) -> None:
    (tmp_path / "ok.md").write_text(
        "---\ntitle: T\nsummary: S\npublished: 2026-10-01\n---\nBody"
    )
    repository = InMemoryPostRepository()
    container = Container(
        posts=memory_post_repositories(repository),
        renderer=MarkdownItRenderer(),
        clock=CLOCK,
        posts_are_durable=True,
    )

    assert cli.main(["sync-posts", "--dir", str(tmp_path)], container) == 0
    assert [p.slug for p in asyncio.run(repository.published(CLOCK.now()))] == ["ok"]


def test_unreachable_database_fails_the_sync_cleanly(tmp_path: Path) -> None:
    (tmp_path / "ok.md").write_text("---\ntitle: T\nsummary: S\n---\nBody")

    @asynccontextmanager
    async def unreachable() -> AsyncIterator[PostRepository]:
        raise PostsUnavailable("down")
        yield  # pragma: no cover  (makes this an async generator)

    container = Container(
        posts=unreachable,
        renderer=MarkdownItRenderer(),
        clock=CLOCK,
        posts_are_durable=True,
    )

    assert cli.main(["sync-posts", "--dir", str(tmp_path)], container) == 1


def test_posts_directory_ships_with_the_repo() -> None:
    assert cli.POSTS_DIR.is_dir()

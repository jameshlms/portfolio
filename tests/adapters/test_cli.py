"""The CLI's checks that run before it touches the database."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from app.adapters.cli import commands as cli
from app.adapters.markdown import MarkdownItRenderer
from app.container import Container
from app.ports.driven.blog import PostRepository


@asynccontextmanager
async def _fail_if_opened() -> AsyncIterator[PostRepository]:
    raise AssertionError("the database must not be touched")
    yield  # pragma: no cover  (makes this an async generator)


_CONTAINER = Container(posts=_fail_if_opened, renderer=MarkdownItRenderer())


def test_invalid_post_aborts_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "bad.md").write_text("---\ntitle: No summary\n---\nBody")

    assert cli.main(["sync-posts", "--dir", str(tmp_path)], _CONTAINER) == 1


def test_post_with_a_missing_chart_aborts_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "charted.md").write_text(
        "---\ntitle: T\nsummary: S\n---\n```plotly\nmissing.json\n```\n"
    )

    assert cli.main(["sync-posts", "--dir", str(tmp_path)], _CONTAINER) == 1


def test_missing_directory_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:

    assert cli.main(["sync-posts", "--dir", str(tmp_path / "nope")], _CONTAINER) == 1


def test_valid_posts_need_a_database_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "ok.md").write_text("---\ntitle: T\nsummary: S\n---\nBody")
    monkeypatch.setattr(cli.settings, "database_url", None)

    assert cli.main(["sync-posts", "--dir", str(tmp_path)], _CONTAINER) == 1


def test_posts_directory_ships_with_the_repo() -> None:
    assert cli.POSTS_DIR.is_dir()

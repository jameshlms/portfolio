"""The CLI's checks that run before it touches the database."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from app import cli


def test_invalid_post_aborts_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "bad.md").write_text("---\ntitle: No summary\n---\nBody")
    monkeypatch.setattr(cli, "transaction", _fail_if_called)

    assert cli.main(["sync-posts", "--dir", str(tmp_path)]) == 1


def test_post_with_a_missing_chart_aborts_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "charted.md").write_text(
        "---\ntitle: T\nsummary: S\n---\n```plotly\nmissing.json\n```\n"
    )
    monkeypatch.setattr(cli, "transaction", _fail_if_called)

    assert cli.main(["sync-posts", "--dir", str(tmp_path)]) == 1


def test_missing_directory_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "transaction", _fail_if_called)

    assert cli.main(["sync-posts", "--dir", str(tmp_path / "nope")]) == 1


def test_valid_posts_need_a_database_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "ok.md").write_text("---\ntitle: T\nsummary: S\n---\nBody")
    monkeypatch.setattr(cli.settings, "database_url", None)
    monkeypatch.setattr(cli, "transaction", _fail_if_called)

    assert cli.main(["sync-posts", "--dir", str(tmp_path)]) == 1


def test_unreachable_database_fails_the_sync_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "ok.md").write_text("---\ntitle: T\nsummary: S\n---\nBody")
    monkeypatch.setattr(cli.settings, "database_url", "postgresql+asyncpg://u:p@x/y")
    monkeypatch.setattr(cli, "transaction", _refused)

    assert cli.main(["sync-posts", "--dir", str(tmp_path)]) == 1


@asynccontextmanager
async def _refused() -> AsyncIterator[None]:
    raise ConnectionRefusedError("database down")  # what asyncpg raises
    yield  # pragma: no cover  (makes this an async generator)


def test_posts_directory_ships_with_the_repo() -> None:
    assert cli.POSTS_DIR.is_dir()


def _fail_if_called() -> None:
    raise AssertionError("the database must not be touched")

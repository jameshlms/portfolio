from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.adapters.post_files import read_post_files

_VALID = """---
title: Hello
summary: A first post.
tags: [python]
published: 2026-11-07
---

Some **Markdown**.
"""


def test_reads_every_markdown_file_with_its_name_as_slug(tmp_path: Path) -> None:
    (tmp_path / "hello-world.md").write_text(_VALID)
    (tmp_path / "notes.txt").write_text("not a post")
    (tmp_path / ".gitkeep").write_text("")

    files = read_post_files(tmp_path)

    assert files.invalid == ()
    [post] = files.posts
    assert post.slug == "hello-world"
    assert post.published_at == datetime(2026, 11, 7, tzinfo=UTC)
    assert post.markdown == "Some **Markdown**."


def test_loads_figures_from_the_folder_named_after_the_post(tmp_path: Path) -> None:
    (tmp_path / "hello.md").write_text(_VALID)
    (tmp_path / "hello").mkdir()
    (tmp_path / "hello" / "times.json").write_text('{"data": []}')
    (tmp_path / "hello" / "notes.txt").write_text("ignored")

    [post] = read_post_files(tmp_path).posts

    assert dict(post.figures) == {"times.json": '{"data": []}'}


def test_collects_invalid_files_instead_of_stopping(tmp_path: Path) -> None:
    (tmp_path / "good.md").write_text(_VALID)
    (tmp_path / "no-title.md").write_text(_VALID.replace("title: Hello\n", ""))
    (tmp_path / "bad-yaml.md").write_text("---\ntitle: [unclosed\n---\nBody")

    files = read_post_files(tmp_path)

    assert [p.slug for p in files.posts] == ["good"]
    assert {e.slug: set(e.errors) for e in files.invalid} == {
        "bad-yaml": {"front matter"},
        "no-title": {"title"},
    }


def test_missing_directory_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(NotADirectoryError):
        read_post_files(tmp_path / "nope")

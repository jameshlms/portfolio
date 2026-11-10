"""Command-line entry points.

    python -m app.cli sync-posts [--dir content/blog]

sync-posts makes the blog_posts table match the Markdown files: it adds and
updates posts and removes rows whose file is gone. If any file is invalid it
reports every problem and writes nothing. Runs at pre-deploy, after
`alembic upgrade head`.
"""

import argparse
import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path

import structlog

from app.adapters.markdown import MarkdownItRenderer
from app.adapters.post_files import read_post_files
from app.adapters.sql_posts import SqlPostRepository
from app.config import settings
from app.db import close_engine, transaction
from app.domain.errors import InvalidPost, InvalidPosts
from app.log_config import configure_logging
from app.services.blog import render_posts, sync_posts

POSTS_DIR = Path(__file__).resolve().parent.parent / "content" / "blog"

_log = structlog.get_logger(__name__)


async def _sync_posts(directory: Path) -> int:
    try:
        files = read_post_files(directory)
    except NotADirectoryError:
        _log.error("posts_dir_missing", dir=str(directory))
        return 1
    try:
        posts = render_posts(files.posts, MarkdownItRenderer())
        invalid: tuple[InvalidPost, ...] = files.invalid
    except InvalidPosts as e:
        posts, invalid = (), files.invalid + e.posts
    for error in invalid:
        _log.error("invalid_post", slug=error.slug, errors=dict(error.errors))
    if invalid:
        _log.error("sync_aborted", invalid=len(invalid))
        return 1

    if settings.database_url is None:
        _log.error("database_url_missing")
        return 1

    try:
        async with transaction() as session:
            removed = await sync_posts(posts, SqlPostRepository(session))
    finally:
        await close_engine()

    _log.info(
        "posts_synced",
        posts=len(posts),
        drafts=sum(p.source.published_at is None for p in posts),
        with_charts=sum(p.has_charts for p in posts),
        removed=list(removed),
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    sync = commands.add_parser(
        "sync-posts", help="Store the Markdown posts in the database."
    )
    sync.add_argument(
        "--dir", type=Path, default=POSTS_DIR, help=f"Default: {POSTS_DIR}"
    )
    args = parser.parse_args(argv)

    configure_logging()
    return asyncio.run(_sync_posts(args.dir))


if __name__ == "__main__":
    sys.exit(main())

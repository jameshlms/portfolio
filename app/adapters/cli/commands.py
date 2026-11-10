"""Commands, run through app.__main__ with a bootstrapped Container.

    python -m app sync-posts [--dir content/blog]

sync-posts makes the blog_posts table match the Markdown files: it adds and
updates posts and removes rows whose file is gone. If any file is invalid it
reports every problem and writes nothing. Runs at pre-deploy, after
`alembic upgrade head`.
"""

import argparse
import asyncio
from collections.abc import Sequence
from pathlib import Path

import structlog

from app.adapters.cli.post_files import read_post_files
from app.container import Container
from app.domain.errors import InvalidPost, InvalidPosts
from app.services.blog import render_posts, sync_posts

POSTS_DIR = Path(__file__).resolve().parents[3] / "content" / "blog"

_log = structlog.get_logger(__name__)


async def _sync_posts(directory: Path, container: Container) -> int:
    try:
        files = read_post_files(directory)
    except NotADirectoryError:
        _log.error("posts_dir_missing", dir=str(directory))
        return 1
    try:
        posts = render_posts(files.posts, container.renderer)
        invalid: tuple[InvalidPost, ...] = files.invalid
    except InvalidPosts as e:
        posts, invalid = (), files.invalid + e.posts
    for error in invalid:
        _log.error("invalid_post", slug=error.slug, errors=dict(error.errors))
    if invalid:
        _log.error("sync_aborted", invalid=len(invalid))
        return 1

    # Without a database the container's posts live in memory and would vanish.
    if not container.posts_are_durable:
        _log.error("database_url_missing")
        return 1

    async with container.posts() as repository:
        removed = await sync_posts(posts, repository)

    _log.info(
        "posts_synced",
        posts=len(posts),
        drafts=sum(p.source.published_at is None for p in posts),
        with_charts=sum(p.has_charts for p in posts),
        removed=list(removed),
    )
    return 0


async def _run(args: argparse.Namespace, container: Container) -> int:
    try:
        return await _sync_posts(args.dir, container)
    finally:
        await container.close()


def main(argv: Sequence[str], container: Container) -> int:
    """Run one command against `container`'s ports, then close it. Returns the exit code."""
    parser = argparse.ArgumentParser(prog="python -m app")
    commands = parser.add_subparsers(dest="command", required=True)
    sync = commands.add_parser(
        "sync-posts", help="Store the Markdown posts in the database."
    )
    sync.add_argument(
        "--dir", type=Path, default=POSTS_DIR, help=f"Default: {POSTS_DIR}"
    )
    args = parser.parse_args(argv)
    return asyncio.run(_run(args, container))

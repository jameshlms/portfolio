"""What the blog needs from outside: somewhere to keep posts, a Markdown renderer."""

from collections.abc import Callable, Sequence
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Protocol

from app.domain.blog import Post, PostSource, PostSummary, RenderedBody, RenderedPost


class MarkdownRenderer(Protocol):
    def render(self, post: PostSource) -> RenderedBody:
        """The post's body as HTML. Raises InvalidPost if the body can't be rendered
        (e.g. it embeds a chart whose figure is missing or malformed)."""
        ...


class PostRepository(Protocol):
    """Where posts are kept. "Published" means published_at is set and not after `as_of`.

    Every method raises PostsUnavailable, never a storage-specific error, when the
    store can't be reached.
    """

    async def published(self, as_of: datetime) -> tuple[PostSummary, ...]:
        """Published posts, newest first."""
        ...

    async def get_published(self, slug: str, as_of: datetime) -> Post | None: ...

    async def replace_all(self, posts: Sequence[RenderedPost]) -> tuple[str, ...]:
        """Store exactly these posts, drafts included; returns the slugs removed."""
        ...


# Opens a PostRepository for one unit of work: `async with posts() as repository:`.
# Writes inside the block are kept only if it exits without an error. Raises
# PostsUnavailable if they can't be kept.
type PostRepositoryScope = Callable[[], AbstractAsyncContextManager[PostRepository]]

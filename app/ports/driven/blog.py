"""What the blog needs from outside: somewhere to keep posts, a Markdown renderer."""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from app.domain.blog import Post, PostSource, PostSummary, RenderedBody, RenderedPost


class MarkdownRenderer(Protocol):
    def render(self, post: PostSource) -> RenderedBody:
        """The post's body as HTML. Raises InvalidPost if the body can't be rendered
        (e.g. it embeds a chart whose figure is missing or malformed)."""
        ...


class PostRepository(Protocol):
    """Where posts are kept. "Published" means published_at is set and not after `as_of`."""

    async def published(self, as_of: datetime) -> tuple[PostSummary, ...]:
        """Published posts, newest first."""
        ...

    async def get_published(self, slug: str, as_of: datetime) -> Post | None: ...

    async def replace_all(self, posts: Sequence[RenderedPost]) -> tuple[str, ...]:
        """Store exactly these posts, drafts included; returns the slugs removed."""
        ...

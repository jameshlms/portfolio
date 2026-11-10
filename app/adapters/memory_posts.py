"""PostRepository held in memory: for tests, and for running without a database."""

from collections.abc import Iterable, Sequence
from datetime import datetime

from app.domain.blog import Post, PostSummary, RenderedPost


class InMemoryPostRepository:
    def __init__(self, posts: Iterable[RenderedPost] = ()) -> None:
        self._posts: dict[str, RenderedPost] = {p.source.slug: p for p in posts}

    async def published(self, as_of: datetime) -> tuple[PostSummary, ...]:
        posts = (_to_post(p) for p in self._posts.values() if _is_live(p, as_of))
        return tuple(
            PostSummary(
                slug=p.slug,
                title=p.title,
                summary=p.summary,
                tags=p.tags,
                published_at=p.published_at,
                revised_at=p.revised_at,
            )
            for p in sorted(posts, key=lambda p: p.published_at, reverse=True)
        )

    async def get_published(self, slug: str, as_of: datetime) -> Post | None:
        post = self._posts.get(slug)
        return _to_post(post) if post and _is_live(post, as_of) else None

    async def replace_all(self, posts: Sequence[RenderedPost]) -> tuple[str, ...]:
        incoming = {p.source.slug: p for p in posts}
        removed = tuple(sorted(self._posts.keys() - incoming.keys()))
        self._posts = incoming
        return removed


def _is_live(post: RenderedPost, as_of: datetime) -> bool:
    published_at = post.source.published_at
    return published_at is not None and published_at <= as_of


def _to_post(post: RenderedPost) -> Post:
    s = post.source
    assert s.published_at is not None  # only called on live posts
    return Post(
        slug=s.slug,
        title=s.title,
        summary=s.summary,
        tags=s.tags,
        published_at=s.published_at,
        revised_at=s.revised_at,
        html=post.html,
        has_charts=post.has_charts,
    )

"""Blog use cases: render and store posts, read the index and single posts.

Thin orchestration over the domain (app.domain.blog) and the driven ports
(app.ports.driven.blog). The CLI reads post files and calls `render_posts` then
`sync_posts`; the blog routes call `blog_index` and `get_post`.
"""

from collections.abc import Iterable, Sequence
from datetime import datetime

from app.domain.blog import BlogIndex, Post, PostSource, RenderedPost, build_index
from app.domain.errors import InvalidPost, InvalidPosts, PostNotFound
from app.ports.driven.blog import MarkdownRenderer, PostRepository


def render_posts(
    sources: Iterable[PostSource], renderer: MarkdownRenderer
) -> tuple[RenderedPost, ...]:
    """Render every post. Raises InvalidPosts listing every post that failed."""
    results = tuple(_render(source, renderer) for source in sources)
    if invalid := [r for r in results if isinstance(r, InvalidPost)]:
        raise InvalidPosts(invalid)
    return tuple(r for r in results if isinstance(r, RenderedPost))


def _render(
    source: PostSource, renderer: MarkdownRenderer
) -> RenderedPost | InvalidPost:
    try:
        body = renderer.render(source)
    except InvalidPost as e:
        return e
    return RenderedPost(source, body.html, body.has_charts)


async def sync_posts(
    posts: Sequence[RenderedPost], repository: PostRepository
) -> tuple[str, ...]:
    """Make the stored posts exactly `posts`; returns the slugs removed."""
    return await repository.replace_all(posts)


async def blog_index(
    repository: PostRepository, as_of: datetime, tag: str | None = None
) -> BlogIndex:
    """Published posts, optionally only those tagged `tag`. Raises UnknownTag."""
    return build_index(await repository.published(as_of), tag)


async def get_post(repository: PostRepository, slug: str, as_of: datetime) -> Post:
    """A published post. Raises PostNotFound."""
    post = await repository.get_published(slug, as_of)
    if post is None:
        raise PostNotFound(slug)
    return post

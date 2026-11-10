"""Blog use cases: render and store posts, read the index and single posts.

Thin orchestration over the domain (app.domain.blog) and the driven ports
(app.ports.driven.blog). The CLI reads post files and calls `render_posts` then
`sync_posts`; the blog routes call `blog_index` and `get_post`, and the crawler files
`list_published_posts`. "Published" is judged at `clock.now()`.
"""

from collections.abc import Iterable, Sequence

from app.domain.blog import (
    BlogIndex,
    Post,
    PostSource,
    PostSummary,
    RenderedPost,
    build_index,
)
from app.domain.errors import InvalidPost, InvalidPosts, PostNotFound
from app.ports.driven.blog import MarkdownRenderer, PostRepository
from app.ports.driven.clock import Clock


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


async def list_published_posts(
    repository: PostRepository, clock: Clock
) -> tuple[PostSummary, ...]:
    """Every published post, newest first."""
    return await repository.published(clock.now())


async def blog_index(
    repository: PostRepository, clock: Clock, tag: str | None = None
) -> BlogIndex:
    """Published posts, optionally only those tagged `tag`. Raises UnknownTag."""
    return build_index(await repository.published(clock.now()), tag)


async def get_post(repository: PostRepository, clock: Clock, slug: str) -> Post:
    """A published post. Raises PostNotFound."""
    post = await repository.get_published(slug, clock.now())
    if post is None:
        raise PostNotFound(slug)
    return post

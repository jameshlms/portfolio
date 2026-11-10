"""Blog: post records, the rules a post must follow, what the blog needs from
outside, and the use cases built on them.

Pure: no I/O and no framework imports. A post is written as Markdown with front
matter in content/blog/; the CLI reads the files, `parse_post` checks each one,
`render_posts` renders them through a `MarkdownRenderer` and `sync_posts` stores
them through a `PostRepository`. Pages read published posts back with
`blog_index`, `get_post` and `list_published_posts`. "Published" is judged at
`as_of`, which defaults to now.

The adapters in app.adapters implement the Protocols (sql_posts / memory_posts,
markdown); app.deps chooses which one a request gets.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from types import MappingProxyType
from typing import Any, Protocol

from app.services.errors import InvalidPost, InvalidPosts, PostNotFound, UnknownTag

SLUG_MAX = 200
TITLE_MAX = 500
SUMMARY_MAX = 300  # long enough for a meta description, short enough to stay one

_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_FIELDS = frozenset({"title", "summary", "tags", "published", "updated"})


# --- Records -------------------------------------------------------------------


@dataclass(frozen=True)
class PostSource:
    """A post as written: front matter checked, body still Markdown."""

    slug: str
    title: str
    summary: str
    tags: tuple[str, ...]
    published_at: datetime | None  # None: a draft, stored but never shown
    revised_at: datetime | None  # the author's "updated" date, if any
    markdown: str
    # Chart figures the body can embed: file name -> Plotly figure JSON.
    figures: Mapping[str, str] = MappingProxyType({})  # read-only, so safe to share


@dataclass(frozen=True)
class RenderedBody:
    html: str
    has_charts: bool = False  # the body embeds charts


@dataclass(frozen=True)
class RenderedPost:
    """A post ready to store: its source plus the HTML its Markdown renders to."""

    source: PostSource
    html: str
    has_charts: bool = False


@dataclass(frozen=True)
class PostSummary:
    """A published post as listed: everything but the body."""

    slug: str
    title: str
    summary: str
    tags: tuple[str, ...]
    published_at: datetime
    revised_at: datetime | None

    @property
    def last_modified(self) -> datetime:
        return self.revised_at or self.published_at


@dataclass(frozen=True)
class Post(PostSummary):
    """A published post with its rendered body."""

    html: str
    has_charts: bool = False


@dataclass(frozen=True)
class TagCount:
    tag: str
    posts: int


@dataclass(frozen=True)
class BlogIndex:
    """What the blog index shows: the (possibly filtered) posts and every tag."""

    posts: tuple[PostSummary, ...]
    tags: tuple[TagCount, ...]
    tag: str | None = None  # the tag being filtered on


# --- What the blog needs from outside ------------------------------------


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


# --- Rules ---------------------------------------------------------------------


def parse_post(
    slug: str,
    metadata: Mapping[Any, object],  # parsed YAML: keys needn't be strings
    markdown: str,
    figures: Mapping[str, str] = MappingProxyType({}),
) -> PostSource:
    """Check one post's front matter. Raises InvalidPost listing every problem.

    `figures` are the chart files beside the post (name -> Plotly figure JSON);
    the renderer checks the ones the body embeds.
    """
    errors: dict[str, str] = {}

    if not _is_slug(slug):
        errors["slug"] = (
            f"Use lowercase letters, digits and single hyphens, at most {SLUG_MAX} "
            "characters (it's the file name)."
        )
    # str(): YAML keys needn't be strings (`2026: x`), and mixed types don't sort.
    for field in sorted(str(k) for k in metadata.keys() - _FIELDS):
        errors[field] = f"Unknown field. Allowed: {', '.join(sorted(_FIELDS))}."

    title = _text(metadata.get("title"), "title", TITLE_MAX, errors)
    summary = _text(metadata.get("summary"), "summary", SUMMARY_MAX, errors)
    tags = _tags(metadata.get("tags", ()), errors)
    published_at = _moment(metadata.get("published"), "published", errors)
    revised_at = _moment(metadata.get("updated"), "updated", errors)

    if revised_at and published_at is None:
        errors["updated"] = "A draft can't have an updated date; set published first."
    elif revised_at and published_at and revised_at < published_at:
        errors["updated"] = "Must be on or after the published date."
    if not markdown.strip():
        errors["body"] = "The post has no content."

    if errors:
        raise InvalidPost(slug, errors)
    return PostSource(
        slug=slug,
        title=title,
        summary=summary,
        tags=tags,
        published_at=published_at,
        revised_at=revised_at,
        markdown=markdown,
        figures=MappingProxyType(dict(figures)),
    )


def normalize_tag(tag: str) -> str:
    return tag.strip().lower()


def _is_slug(value: str) -> bool:
    return len(value) <= SLUG_MAX and _SLUG.fullmatch(value) is not None


def _text(value: object, field: str, limit: int, errors: dict[str, str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors[field] = "Required."
        return ""
    text = " ".join(value.split())
    if len(text) > limit:
        errors[field] = f"At most {limit} characters."
    return text


def _tags(value: object, errors: dict[str, str]) -> tuple[str, ...]:
    if not isinstance(value, list | tuple) or not all(
        isinstance(t, str) for t in value
    ):
        errors["tags"] = "A list of tags, e.g. [python, data-engineering]."
        return ()
    tags = tuple(dict.fromkeys(normalize_tag(t) for t in value))  # dedupe, keep order
    if bad := [t for t in tags if not _is_slug(t)]:
        errors["tags"] = (
            f"Tags are lowercase words joined by hyphens; not {', '.join(bad)}."
        )
    return tags


def _moment(value: object, field: str, errors: dict[str, str]) -> datetime | None:
    """A date or datetime from front matter, in UTC. Dates mean midnight UTC."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            errors[field] = "Use a date like 2026-11-07 or 2026-11-07T09:30:00Z."
            return None
    if isinstance(value, datetime):  # before date: datetime is a date subclass
        return (
            value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        )
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    errors[field] = "Use a date like 2026-11-07 or 2026-11-07T09:30:00Z."
    return None


def build_index(posts: Sequence[PostSummary], tag: str | None = None) -> BlogIndex:
    """The index over published `posts`, optionally only those tagged `tag`.

    Tags are counted over every post, most used first, so the filter always offers
    them all. Raises UnknownTag if no post carries `tag`.
    """
    counts = Counter(t for post in posts for t in post.tags)
    tags = tuple(
        TagCount(t, n) for t, n in sorted(counts.items(), key=lambda c: (-c[1], c[0]))
    )
    if tag is None:
        return BlogIndex(posts=tuple(posts), tags=tags)

    tag = normalize_tag(tag)
    if tag not in counts:
        raise UnknownTag(tag)
    return BlogIndex(posts=tuple(p for p in posts if tag in p.tags), tags=tags, tag=tag)


# --- Use cases -----------------------------------------------------------------


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
    repository: PostRepository, *, as_of: datetime | None = None
) -> tuple[PostSummary, ...]:
    """Every published post, newest first."""
    return await repository.published(as_of or datetime.now(UTC))


async def blog_index(
    repository: PostRepository, tag: str | None = None, *, as_of: datetime | None = None
) -> BlogIndex:
    """Published posts, optionally only those tagged `tag`. Raises UnknownTag."""
    return build_index(await list_published_posts(repository, as_of=as_of), tag)


async def get_post(
    repository: PostRepository, slug: str, *, as_of: datetime | None = None
) -> Post:
    """A published post. Raises PostNotFound."""
    post = await repository.get_published(slug, as_of or datetime.now(UTC))
    if post is None:
        raise PostNotFound(slug)
    return post

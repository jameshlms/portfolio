"""Blog: post records and the rules a post must follow.

Pure: no I/O and no framework imports. A post is written as Markdown with front
matter; `parse_post` checks it into a `PostSource`, rendering turns that into a
`RenderedPost` for storage, and published posts come back as `PostSummary` /
`Post`. `build_index` is the blog index over a set of published posts.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from types import MappingProxyType

from app.domain.errors import InvalidPost, UnknownTag

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
    has_charts: bool = False  # the page must load plotly.js


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


# --- Rules ---------------------------------------------------------------------


def parse_post(
    slug: str,
    metadata: Mapping[str, object],
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
    for field in sorted(metadata.keys() - _FIELDS):
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

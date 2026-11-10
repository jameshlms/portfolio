"""Builders for blog records, so tests only spell out the fields they're about."""

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from app.services.blog import PostSource, RenderedPost

PUBLISHED = datetime(2026, 10, 1, tzinfo=UTC)
NOW = datetime(2026, 11, 7, 12, tzinfo=UTC)


def source(slug: str = "first-post", **fields: Any) -> PostSource:
    base = PostSource(
        slug=slug,
        title=f"Title of {slug}",
        summary=f"Summary of {slug}.",
        tags=(),
        published_at=PUBLISHED,
        revised_at=None,
        markdown=f"Body of {slug}.",
    )
    return replace(base, **fields)


def rendered(slug: str = "first-post", **fields: Any) -> RenderedPost:
    s = source(slug, **fields)
    return RenderedPost(s, f"<p>{s.markdown}</p>\n")

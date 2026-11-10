"""Builders for blog records and a fixed clock, so tests only spell out what they're about."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

from app.domain.blog import PostSource, RenderedPost

PUBLISHED = datetime(2026, 10, 1, tzinfo=UTC)
NOW = datetime(2026, 11, 7, 12, tzinfo=UTC)


@dataclass(frozen=True)
class FixedClock:
    """A Clock stopped at `moment`."""

    moment: datetime = NOW

    def now(self) -> datetime:
        return self.moment


CLOCK = FixedClock()


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

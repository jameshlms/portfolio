"""Open Graph <meta property="..."> tags (https://ogp.me).

Fields are snake_case in Python and serialize to namespaced property names:
`site_name` -> "og:site_name", `image_alt` -> "og:image:alt", `tags` -> "article:tag".
Field order is output order, which matters: og:image:* properties must follow og:image.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

type MetaProperty = tuple[str, str]  # (property, content)


def _namespaced(namespace: str) -> Callable[[str], str]:
    return lambda field_name: f"{namespace}:{field_name}"


class _MetaProperties(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
    )

    def meta_properties(self) -> tuple[MetaProperty, ...]:
        """One (property, content) pair per tag; a list field repeats its property."""
        dumped: dict[str, Any] = self.model_dump(mode="json", exclude_none=True)
        return tuple(
            (prop, str(content))
            for prop, value in dumped.items()
            for content in (value if isinstance(value, list) else (value,))
        )


class OpenGraph(_MetaProperties):
    model_config = ConfigDict(alias_generator=_namespaced("og"))

    type: Literal["website", "article", "profile"] = "website"
    title: str
    description: str
    url: str | None = None  # left out on noindex pages, which have no canonical URL
    site_name: str
    locale: str = "en_US"
    image: str | None = None
    image_width: int | None = Field(
        default=None,
        serialization_alias="og:image:width",
        validation_alias="og:image:width",
    )
    image_height: int | None = Field(
        default=None,
        serialization_alias="og:image:height",
        validation_alias="og:image:height",
    )
    image_alt: str | None = Field(
        default=None,
        serialization_alias="og:image:alt",
        validation_alias="og:image:alt",
    )


class OpenGraphArticle(_MetaProperties):
    model_config = ConfigDict(alias_generator=_namespaced("article"))

    published_time: datetime | None = None
    modified_time: datetime | None = None
    author: str | None = None  # URL of the author's profile page
    tags: tuple[str, ...] = Field(
        default=(), serialization_alias="article:tag", validation_alias="article:tag"
    )

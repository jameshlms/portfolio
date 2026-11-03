"""schema.org nodes for JSON-LD structured data.

Fields are snake_case in Python. JSON-LD keywords serialize with their "@" prefix
(`type` -> "@type", `id` -> "@id"); schema.org properties serialize camelCase
(`same_as` -> "sameAs").
"""

from collections.abc import Iterable
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

# JSON-LD keywords: defined by the format itself, so "@"-prefixed to never collide with
# a vocabulary property of the same name.
_KEYWORDS = {"type": "@type", "id": "@id"}


def _alias(field_name: str) -> str:
    return _KEYWORDS.get(field_name, to_camel(field_name))


class _SchemaOrgModel(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",  # a misspelled property fails here instead of shipping
        alias_generator=_alias,
        validate_by_name=True,
        serialize_by_alias=True,
    )

    def to_json_ld(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)


class Ref(_SchemaOrgModel):
    """A reference to a node defined elsewhere in the @graph: {"@id": ...}."""

    id: str


class Node(_SchemaOrgModel):
    type: str
    id: str | None = None


class WebSite(Node):
    type: Literal["WebSite"] = "WebSite"
    url: str
    name: str
    in_language: str
    publisher: Ref


class Person(Node):
    type: Literal["Person"] = "Person"
    name: str
    url: str
    image: str | None = None
    same_as: tuple[str, ...] | None = None


type PageType = Literal["WebPage", "ProfilePage", "ContactPage", "CollectionPage"]


class WebPage(Node):
    type: PageType = "WebPage"
    url: str
    name: str
    description: str
    in_language: str
    is_part_of: Ref
    main_entity: Ref | None = None


class ListItem(_SchemaOrgModel):
    type: Literal["ListItem"] = "ListItem"
    position: int
    name: str
    item: str


class BreadcrumbList(Node):
    type: Literal["BreadcrumbList"] = "BreadcrumbList"
    item_list_element: tuple[ListItem, ...]


class CreativeWork(Node):
    type: Literal["CreativeWork"] = "CreativeWork"
    url: str
    name: str
    description: str
    author: Ref
    date_published: datetime | None = None
    date_modified: datetime | None = None


def json_ld_document(nodes: Iterable[Node]) -> dict[str, Any]:
    """A JSON-LD document: the nodes share one @context and link to each other by @id."""
    return {
        "@context": "https://schema.org",
        "@graph": [node.to_json_ld() for node in nodes],
    }

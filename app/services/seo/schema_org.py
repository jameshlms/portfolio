"""schema.org nodes for JSON-LD structured data.

Fields are snake_case in Python. JSON-LD keywords serialize with their "@" prefix
(`type` -> "@type", `graph` -> "@graph"); schema.org properties serialize camelCase
(`same_as` -> "sameAs"). Parsing accepts the JSON-LD names, so documents round-trip:
`JsonLdDocument.from_json_ld(doc.to_json_ld()) == doc`.

The class hierarchy mirrors schema.org's (Thing -> CreativeWork -> WebPage, ...).
Abstract bases keep `type: str`; only concrete leaves narrow it to a Literal, which is
what the discriminated union in JsonLdDocument keys on.
"""

from collections.abc import Mapping
from datetime import datetime
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

SCHEMA_ORG = "https://schema.org"

# JSON-LD keywords: defined by the format itself, so "@"-prefixed to never collide with
# a vocabulary property of the same name.
_KEYWORDS = {"context": "@context", "graph": "@graph", "type": "@type", "id": "@id"}


def _alias(field_name: str) -> str:
    return _KEYWORDS.get(field_name, to_camel(field_name))


class JsonLdModel(BaseModel):
    """Base for anything written as JSON-LD."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",  # a misspelled property fails here instead of shipping
        alias_generator=_alias,
        validate_by_name=True,  # build with Python names...
        validate_by_alias=True,  # ...or parse JSON-LD names
        serialize_by_alias=True,
    )

    def to_json_ld(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)

    @classmethod
    def from_json_ld(cls, data: Mapping[str, Any]) -> Self:
        return cls.model_validate(data)


class Ref(JsonLdModel):
    """A reference to a node defined elsewhere in the @graph: {"@id": ...}."""

    id: str


# --- Abstract bases (schema.org's type hierarchy) -----------------------------


class Thing(JsonLdModel):
    """schema.org/Thing: properties every node can carry."""

    type: str
    id: str | None = None
    name: str | None = None
    url: str | None = None
    description: str | None = None
    image: str | None = None
    same_as: tuple[str, ...] | None = None

    def ref(self) -> Ref:
        if self.id is None:
            raise ValueError(f"{self.type} has no @id to reference")
        return Ref(id=self.id)


class BaseCreativeWork(Thing):
    """schema.org/CreativeWork properties, shared by websites, pages and works."""

    in_language: str | None = None
    author: Ref | None = None
    publisher: Ref | None = None
    is_part_of: Ref | None = None
    main_entity: Ref | None = None
    date_published: datetime | None = None
    date_modified: datetime | None = None


# --- Concrete node types -------------------------------------------------------


class Person(Thing):
    type: Literal["Person"] = "Person"
    name: str
    url: str


class WebSite(BaseCreativeWork):
    type: Literal["WebSite"] = "WebSite"
    name: str
    url: str


type PageType = Literal["WebPage", "ProfilePage", "ContactPage", "CollectionPage"]


class WebPage(BaseCreativeWork):
    type: PageType = "WebPage"
    name: str
    url: str
    description: str


class CreativeWork(BaseCreativeWork):
    type: Literal["CreativeWork"] = "CreativeWork"
    name: str
    url: str


class ListItem(Thing):
    type: Literal["ListItem"] = "ListItem"
    position: int
    name: str
    item: str


class BreadcrumbList(Thing):
    type: Literal["BreadcrumbList"] = "BreadcrumbList"
    item_list_element: tuple[ListItem, ...]


# --- Document ------------------------------------------------------------------

# Every type that may appear at the top of an @graph; "@type" picks the class when parsing.
type GraphNode = Annotated[
    WebSite | Person | WebPage | CreativeWork | BreadcrumbList,
    Field(discriminator="type"),
]


class JsonLdDocument(JsonLdModel):
    """A JSON-LD document: nodes sharing one @context, linked to each other by @id."""

    context: Literal["https://schema.org"] = SCHEMA_ORG
    graph: tuple[GraphNode, ...]

"""schema.org nodes for JSON-LD structured data.

Fields are snake_case in Python. JSON-LD keywords serialize with their "@" prefix,
scoped to the model they belong to (`type`/`id` -> "@type"/"@id" on nodes,
`context`/`graph` -> "@context"/"@graph" on the document); schema.org properties
serialize camelCase (`same_as` -> "sameAs"). Parsing accepts the JSON-LD names, so
documents round-trip:
`JsonLdDocument.from_json_ld(doc.to_json_ld()) == doc`.

The class hierarchy mirrors schema.org's (Thing -> CreativeWork -> WebSite, ...), and
each class narrows `type` to its own Literal, which is what the discriminated union in
JsonLdDocument keys on. A property is declared where it becomes required, never
redeclared narrower further down: type checkers reject a required field overriding an
optional one.
"""

# Narrowing `type` per subclass (str -> Literal["Person"], Literal["CreativeWork"] ->
# Literal["WebSite"]) is the discriminator design, but pyright treats model fields as
# mutable and reports any narrowed override. Pydantic validates the result at runtime.
# pyright: reportIncompatibleVariableOverride=false

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

SCHEMA_ORG = "https://schema.org"

# JSON-LD keywords: defined by the format itself, so "@"-prefixed to never collide with
# a vocabulary property of the same name. Each kind of model maps only its own keywords,
# so a node field named `context` or `graph` stays a plain "context" / "graph" property.
_NODE_KEYWORDS: Mapping[str, str] = {"type": "@type", "id": "@id"}
_DOCUMENT_KEYWORDS: Mapping[str, str] = {"context": "@context", "graph": "@graph"}


def _aliases(keywords: Mapping[str, str]) -> Callable[[str], str]:
    return lambda field_name: keywords.get(field_name, to_camel(field_name))


class JsonLdModel(BaseModel):
    """Base for anything written as JSON-LD. Nodes by default; see JsonLdDocument."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",  # a misspelled property fails here instead of shipping
        alias_generator=_aliases(_NODE_KEYWORDS),
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


# --- Node types (schema.org's type hierarchy) -----------------------------------


class Thing(JsonLdModel):
    """schema.org/Thing: properties any node may carry and no subclass requires."""

    type: str
    id: str | None = None
    image: str | None = None
    same_as: tuple[str, ...] | None = None

    def ref(self) -> Ref:
        if self.id is None:
            raise ValueError(f"{self.type} has no @id to reference")
        return Ref(id=self.id)


class Person(Thing):
    type: Literal["Person"] = "Person"
    name: str
    url: str


class CreativeWork(Thing):
    """schema.org/CreativeWork, and the parent of websites and pages."""

    type: Literal["CreativeWork"] = "CreativeWork"
    name: str
    url: str
    description: str | None = None
    in_language: str | None = None
    author: Ref | None = None
    publisher: Ref | None = None
    is_part_of: Ref | None = None
    main_entity: Ref | None = None
    date_published: datetime | None = None
    date_modified: datetime | None = None


class WebSite(CreativeWork):
    type: Literal["WebSite"] = "WebSite"


type PageType = Literal["WebPage", "ProfilePage", "ContactPage", "CollectionPage"]


class WebPage(CreativeWork):
    type: PageType = "WebPage"


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

    model_config = ConfigDict(alias_generator=_aliases(_DOCUMENT_KEYWORDS))

    context: Literal["https://schema.org"] = SCHEMA_ORG
    graph: tuple[GraphNode, ...]

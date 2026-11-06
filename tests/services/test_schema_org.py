from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.services.schema_org import (
    BreadcrumbList,
    CreativeWork,
    JsonLdDocument,
    ListItem,
    Person,
    Ref,
    WebPage,
    WebSite,
)


def test_keywords_and_camel_case_aliases() -> None:
    person = Person(id="https://x/#person", name="J", url="https://x/", same_as=("a",))

    assert person.to_json_ld() == {
        "@type": "Person",
        "@id": "https://x/#person",
        "name": "J",
        "url": "https://x/",
        "sameAs": ["a"],
    }


def test_unset_optional_properties_are_omitted() -> None:
    page = WebPage(
        url="u", name="n", description="d", in_language="en", is_part_of=Ref(id="s")
    )

    assert "mainEntity" not in page.to_json_ld()
    assert page.to_json_ld()["isPartOf"] == {"@id": "s"}


def test_datetimes_serialize_as_iso_8601() -> None:
    work = CreativeWork(
        url="u",
        name="n",
        description="d",
        author=Ref(id="p"),
        date_published=datetime(2026, 10, 1, 9, 0, tzinfo=UTC),
    )

    assert work.to_json_ld()["datePublished"] == "2026-10-01T09:00:00Z"


def test_misspelled_property_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Person(name="J", url="u", sameas=("a",))  # type: ignore[call-arg]


def test_page_type_is_restricted_to_known_page_types() -> None:
    with pytest.raises(ValidationError):
        WebPage(
            type="Webpage",  # type: ignore[arg-type]
            url="u",
            name="n",
            description="d",
            in_language="en",
            is_part_of=Ref(id="s"),
        )


def _document() -> JsonLdDocument:
    person = Person(id="https://x/#person", name="J", url="https://x/", same_as=("a",))
    site = WebSite(
        id="https://x/#website", name="J", url="https://x/", publisher=person.ref()
    )
    page = WebPage(
        type="ProfilePage",
        url="https://x/about",
        name="About",
        description="d",
        is_part_of=site.ref(),
        main_entity=person.ref(),
        date_modified=datetime(2026, 10, 1, 9, 0, tzinfo=UTC),
    )
    crumbs = BreadcrumbList(
        item_list_element=(ListItem(position=1, name="Home", item="https://x/"),)
    )
    return JsonLdDocument(graph=(site, person, page, crumbs))


def test_document_wraps_each_node_in_one_graph() -> None:
    doc = _document()

    assert doc.to_json_ld() == {
        "@context": "https://schema.org",
        "@graph": [node.to_json_ld() for node in doc.graph],
    }


def test_document_round_trips_through_json_ld() -> None:
    doc = _document()

    parsed = JsonLdDocument.from_json_ld(doc.to_json_ld())

    assert parsed == doc
    # "@type" picks the class: ProfilePage parses as a WebPage, not a generic node.
    assert [type(node).__name__ for node in parsed.graph] == [
        "WebSite",
        "Person",
        "WebPage",
        "BreadcrumbList",
    ]
    assert parsed.graph[2].type == "ProfilePage"


def test_unknown_graph_node_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        JsonLdDocument.from_json_ld(
            {"@context": "https://schema.org", "@graph": [{"@type": "Robot"}]}
        )


def test_ref_points_at_the_node_id() -> None:
    assert Person(id="https://x/#p", name="J", url="u").ref() == Ref(id="https://x/#p")


def test_ref_needs_an_id() -> None:
    with pytest.raises(ValueError, match="no @id"):
        Person(name="J", url="u").ref()


def test_unset_same_as_is_omitted() -> None:
    assert "sameAs" not in Person(name="J", url="u").to_json_ld()


def test_websites_and_pages_are_creative_works() -> None:
    site = WebSite(name="J", url="https://x/")
    page = WebPage(name="About", url="https://x/about")

    assert isinstance(site, CreativeWork)
    assert isinstance(page, CreativeWork)
    # Each still serializes as its own @type, not its parent's.
    assert site.to_json_ld()["@type"] == "WebSite"
    assert JsonLdDocument(graph=(page,)).to_json_ld()["@graph"][0]["@type"] == "WebPage"

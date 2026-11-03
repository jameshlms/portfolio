from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.services.schema_org import CreativeWork, Graph, Person, Ref, WebPage


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


def test_graph_serializes_every_node_as_its_own_class() -> None:
    person = Person(id="https://x/#person", name="J", url="https://x/")
    page = WebPage(
        url="u",
        name="n",
        description="d",
        in_language="en",
        is_part_of=Ref(id="s"),
        main_entity=Ref(id=person.id),
    )

    assert Graph(graph=(person, page)).to_json_ld() == {
        "@context": "https://schema.org",
        "@graph": [person.to_json_ld(), page.to_json_ld()],
    }
    # Subclass-only fields survive, rather than being cut down to Node's.
    assert Graph(graph=(person,)).to_json_ld()["@graph"][0]["name"] == "J"


def test_unset_same_as_is_omitted() -> None:
    assert "sameAs" not in Person(name="J", url="u").to_json_ld()

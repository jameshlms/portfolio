from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.adapters.http.presentation.open_graph import OpenGraph, OpenGraphArticle


def test_fields_serialize_to_namespaced_properties_in_order() -> None:
    og = OpenGraph(
        title="About",
        description="d",
        url="https://x/about",
        site_name="J",
        image="https://x/a.png",
        image_alt="A",
    )

    assert og.meta_properties() == (
        ("og:type", "website"),
        ("og:title", "About"),
        ("og:description", "d"),
        ("og:url", "https://x/about"),
        ("og:site_name", "J"),
        ("og:locale", "en_US"),
        ("og:image", "https://x/a.png"),
        ("og:image:alt", "A"),
    )


def test_unset_properties_are_omitted() -> None:
    props = dict(OpenGraph(title="t", description="d", site_name="J").meta_properties())

    assert "og:url" not in props
    assert "og:image" not in props


def test_article_repeats_tag_property_per_tag() -> None:
    article = OpenGraphArticle(
        published_time=datetime(2026, 10, 1, 9, 0, tzinfo=UTC),
        author="https://x/about",
        tags=("python", "seo"),
    )

    assert article.meta_properties() == (
        ("article:published_time", "2026-10-01T09:00:00Z"),
        ("article:author", "https://x/about"),
        ("article:tag", "python"),
        ("article:tag", "seo"),
    )


def test_parses_from_property_names() -> None:
    og = OpenGraph.model_validate(
        {
            "og:title": "t",
            "og:description": "d",
            "og:site_name": "J",
            "og:image:alt": "A",
        }
    )

    assert og.image_alt == "A"


def test_misspelled_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        OpenGraph(title="t", description="d", site_name="J", imag="x")  # type: ignore[call-arg]

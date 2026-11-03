from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app import paths
from app.config import settings
from app.services import seo
from app.services.seo import (
    EntityDetails,
    Listing,
    Media,
    llms_document,
    sitemap_entries,
)


def test_static_pages_use_absolute_base_url() -> None:
    locs = [e.loc for e in sitemap_entries()]

    assert locs == [f"{settings.base_url}{p}" for p in seo.STATIC_PAGES]


def test_home_is_base_url_with_trailing_slash() -> None:
    assert sitemap_entries()[0].loc == f"{settings.base_url}/"


def test_noindex_pages_are_excluded(monkeypatch: pytest.MonkeyPatch) -> None:
    pages = dict(seo.STATIC_PAGES)
    pages[paths.Page.CONTACT] = replace(pages[paths.Page.CONTACT], noindex=True)
    monkeypatch.setattr(seo, "STATIC_PAGES", pages)

    locs = {e.loc for e in sitemap_entries()}

    assert f"{settings.base_url}{paths.Page.CONTACT}" not in locs
    assert f"{settings.base_url}{paths.Page.ABOUT}" in locs


def test_entities_follow_static_pages_with_lastmod_and_images() -> None:
    updated = datetime(2026, 10, 1, 12, 30, tzinfo=UTC)
    posts = [EntityDetails("/blog/first", updated)]
    projects = [
        EntityDetails(
            "/projects/pipeline",
            updated,
            (Media("/static/images/cover.png"), Media("https://cdn.example.com/a.png")),
        )
    ]

    entries = sitemap_entries(posts, projects)[len(seo.STATIC_PAGES) :]

    assert [e.loc for e in entries] == [
        f"{settings.base_url}/blog/first",
        f"{settings.base_url}/projects/pipeline",
    ]
    assert all(e.lastmod == updated for e in entries)
    assert entries[0].images == ()
    assert entries[1].images == (
        f"{settings.base_url}/static/images/cover.png",
        "https://cdn.example.com/a.png",
    )


def test_llms_document_sections_and_absolute_urls() -> None:
    doc = llms_document([Listing("/blog/first", "First post", "Why I built this.")])

    assert doc.title == settings.site_name
    assert doc.summary == seo.STATIC_PAGES[paths.Page.HOME].description
    assert [s.heading for s in doc.sections] == ["Pages", "Blog", "Optional"]

    pages, blog, _ = doc.sections
    assert f"{settings.base_url}/" not in {
        link.url for link in pages.links
    }  # home is the H1
    assert blog.links[0].url == f"{settings.base_url}/blog/first"
    assert blog.links[0].notes == "Why I built this."


def test_llms_document_omits_empty_blog_section() -> None:
    assert "Blog" not in [s.heading for s in llms_document([]).sections]


def test_llms_document_excludes_noindex_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    pages = dict(seo.STATIC_PAGES)
    pages[paths.Page.CONTACT] = replace(pages[paths.Page.CONTACT], noindex=True)
    monkeypatch.setattr(seo, "STATIC_PAGES", pages)

    titles = {link.title for link in llms_document([]).sections[0].links}

    assert pages[paths.Page.CONTACT].title not in titles

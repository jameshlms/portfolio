from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app import paths
from app.config import settings
from app.services import seo
from app.services.seo import (
    PublishedPage,
    for_error_page,
    for_page,
    llms_document,
    sitemap_urls,
)

UPDATED = datetime(2026, 10, 1, 12, 30, tzinfo=UTC)


def _noindex(monkeypatch: pytest.MonkeyPatch, page: paths.Page) -> None:
    meta = dict(seo.PAGE_META)
    meta[page] = replace(meta[page], noindex=True)
    monkeypatch.setattr(seo, "PAGE_META", meta)


# --- sitemap -----------------------------------------------------------------


def test_sitemap_lists_every_page_as_absolute_url() -> None:
    locs = [url.loc for url in sitemap_urls()]

    assert locs == [f"{settings.base_url}{p}" for p in seo.PAGE_META]


def test_home_is_base_url_with_trailing_slash() -> None:
    assert sitemap_urls()[0].loc == f"{settings.base_url}/"


def test_noindex_pages_are_left_out_of_sitemap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _noindex(monkeypatch, paths.Page.CONTACT)

    locs = {url.loc for url in sitemap_urls()}

    assert f"{settings.base_url}{paths.Page.CONTACT}" not in locs
    assert f"{settings.base_url}{paths.Page.ABOUT}" in locs


def test_published_pages_follow_static_pages_with_lastmod_and_images() -> None:
    posts = [PublishedPage("/blog/first", "First", "Summary.", UPDATED)]
    projects = [
        PublishedPage(
            "/projects/pipeline",
            "Pipeline",
            "Summary.",
            UPDATED,
            ("/static/images/cover.png", "https://cdn.example.com/a.png"),
        )
    ]

    urls = sitemap_urls(posts, projects)[len(seo.PAGE_META) :]

    assert [url.loc for url in urls] == [
        f"{settings.base_url}/blog/first",
        f"{settings.base_url}/projects/pipeline",
    ]
    assert all(url.lastmod == UPDATED for url in urls)
    assert urls[0].images == ()
    assert urls[1].images == (
        f"{settings.base_url}/static/images/cover.png",
        "https://cdn.example.com/a.png",
    )


# --- <head> metadata ---------------------------------------------------------


def test_home_document_title_leads_with_site_name() -> None:
    home = for_page(paths.Page.HOME)

    assert home.document_title == f"{settings.site_name} · {home.title}"


def test_other_document_titles_end_with_site_name() -> None:
    assert for_page(paths.Page.ABOUT).document_title == f"About · {settings.site_name}"


def test_page_structured_data_is_one_linked_graph() -> None:
    graph = for_page(paths.Page.ABOUT).json_ld

    assert graph["@context"] == "https://schema.org"
    nodes = {node["@type"]: node for node in graph["@graph"]}
    assert set(nodes) == {"WebSite", "Person", "ProfilePage", "BreadcrumbList"}
    assert nodes["ProfilePage"]["isPartOf"] == {"@id": seo.WEBSITE_ID}
    assert nodes["ProfilePage"]["mainEntity"] == {"@id": seo.PERSON_ID}
    assert nodes["Person"]["sameAs"] == [settings.github_url, settings.linkedin_url]
    assert [i["item"] for i in nodes["BreadcrumbList"]["itemListElement"]] == [
        f"{settings.base_url}/",
        f"{settings.base_url}/about",
    ]


def test_home_has_no_breadcrumb() -> None:
    types = {node.type for node in for_page(paths.Page.HOME).structured_data}

    assert "BreadcrumbList" not in types


def test_error_pages_are_noindex_without_structured_data() -> None:
    page = for_error_page("Page not found", "Gone.", "/nope")

    assert page.noindex
    assert page.structured_data == ()


# --- llms.txt ----------------------------------------------------------------


def test_llms_document_sections_and_absolute_urls() -> None:
    doc = llms_document(
        [PublishedPage("/blog/first", "First post", "Why I built this.", UPDATED)]
    )

    assert doc.title == settings.site_name
    assert doc.summary == seo.PAGE_META[paths.Page.HOME].description
    assert [s.heading for s in doc.sections] == ["Pages", "Blog", "Optional"]

    pages, blog, _ = doc.sections
    # Home is the H1, so it isn't repeated as a link.
    assert f"{settings.base_url}/" not in {link.url for link in pages.links}
    assert blog.links[0].url == f"{settings.base_url}/blog/first"
    assert blog.links[0].notes == "Why I built this."


def test_llms_document_omits_empty_blog_section() -> None:
    assert "Blog" not in [s.heading for s in llms_document([]).sections]


def test_llms_document_excludes_noindex_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    _noindex(monkeypatch, paths.Page.CONTACT)

    titles = {link.title for link in llms_document([]).sections[0].links}

    assert seo.PAGE_META[paths.Page.CONTACT].title not in titles

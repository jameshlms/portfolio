from collections.abc import Callable
from datetime import UTC, datetime

from app import paths
from app.config import settings
from app.services.seo.page_meta import PAGE_META, PublishedPage
from app.services.seo.sitemap import sitemap_urls

UPDATED = datetime(2026, 10, 1, 12, 30, tzinfo=UTC)


def test_sitemap_lists_every_page_as_absolute_url() -> None:
    locs = [url.loc for url in sitemap_urls()]

    assert locs == [f"{settings.base_url}{p}" for p in PAGE_META]


def test_home_is_base_url_with_trailing_slash() -> None:
    assert sitemap_urls()[0].loc == f"{settings.base_url}/"


def test_noindex_pages_are_left_out_of_sitemap(
    noindex: Callable[[paths.Page], None],
) -> None:
    noindex(paths.Page.CONTACT)

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

    urls = sitemap_urls(posts, projects)[len(PAGE_META) :]

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

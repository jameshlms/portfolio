from collections.abc import Iterator
from datetime import UTC, datetime
from xml.etree import ElementTree

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import settings
from app.paths import Page
from app.routes import seo
from app.services.seo import PAGE_META, SitemapUrl

_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(seo.router)
    with TestClient(app) as c:
        yield c


def test_sitemap_is_valid_cached_xml(client: TestClient) -> None:
    response = client.get("/sitemap.xml")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    assert response.headers["cache-control"] == "public, max-age=3600"

    root = ElementTree.fromstring(response.content)
    locs = [el.text for el in root.findall("sm:url/sm:loc", _NS)]
    assert locs == [f"{settings.base_url}{page}" for page in PAGE_META]


def test_sitemap_escapes_xml_special_characters(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    entry = SitemapUrl(
        f"{settings.base_url}/blog/hello?a=1&b=2",
        datetime(2026, 10, 1, 9, 0, tzinfo=UTC),
    )
    monkeypatch.setattr(seo, "sitemap_urls", lambda: (entry,))

    root = ElementTree.fromstring(
        client.get("/sitemap.xml").content
    )  # raises if "&" is unescaped

    url = root.find("sm:url", _NS)
    assert url is not None
    assert url.findtext("sm:loc", namespaces=_NS) == entry.loc
    assert url.findtext("sm:lastmod", namespaces=_NS) == "2026-10-01"


def test_robots_blocks_admin_and_points_at_sitemap(client: TestClient) -> None:
    response = client.get("/robots.txt")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text.splitlines() == [
        "User-agent: *",
        "Disallow: /admin",
        "",
        f"Sitemap: {settings.base_url}/sitemap.xml",
    ]


def test_llms_txt_follows_spec_layout(client: TestClient) -> None:
    response = client.get("/llms.txt")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.headers["cache-control"] == "public, max-age=3600"

    page_links = [
        f"- [{meta.title}]({settings.base_url}{page}): {meta.description}"
        for page, meta in PAGE_META.items()
        if not meta.noindex and page != Page.HOME
    ]
    assert response.text.splitlines() == [
        f"# {settings.site_name}",
        "",
        f"> {PAGE_META[Page.HOME].description}",
        "",
        "## Pages",
        "",
        *page_links,
        "",
        "## Optional",
        "",
        f"- [GitHub]({settings.github_url})",
        f"- [LinkedIn]({settings.linkedin_url})",
    ]

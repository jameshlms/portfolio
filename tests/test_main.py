"""Smoke tests through the real app: middleware, static mount, routers, error handlers."""

import json
import re
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.paths import Page
from app.services.seo import PAGE_META, for_page


@pytest.fixture
def client() -> Iterator[TestClient]:
    # TrustedHostMiddleware rejects TestClient's default "testserver" host.
    with TestClient(app, base_url="http://localhost") as c:
        yield c


@pytest.mark.parametrize("page", list(PAGE_META))
def test_every_advertised_page_renders(client: TestClient, page: str) -> None:
    response = client.get(page)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


def test_contact_links_to_email_and_linkedin(client: TestClient) -> None:
    html = client.get("/contact").text

    assert f"mailto:{settings.contact_email}" in html
    assert settings.linkedin_url in html


@pytest.mark.parametrize(
    "path", ["/robots.txt", "/sitemap.xml", "/llms.txt", "/static/css/style.css"]
)
def test_root_files_and_static_are_served(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 200


def _head_tag(html: str, pattern: str) -> str:
    match = re.search(pattern, html)
    assert match, pattern
    return match.group(1)


@pytest.mark.parametrize("page", list(PAGE_META))
def test_pages_render_head_metadata_from_seo_context(
    client: TestClient, page: Page
) -> None:
    html = client.get(page).text
    expected = for_page(page)

    assert _head_tag(html, r"<title>(.*?)</title>") == expected.document_title
    assert (
        _head_tag(html, r'<link rel="canonical" href="([^"]+)"') == expected.canonical
    )
    assert (
        _head_tag(html, r'<meta property="og:title" content="([^"]+)"')
        == expected.title
    )
    json_ld = _head_tag(html, r'<script type="application/ld\+json">(.*?)</script>')
    assert json.loads(json_ld) == expected.json_ld


def test_canonical_ignores_trailing_slash_and_query(client: TestClient) -> None:
    html = client.get("/about?utm_source=x").text

    assert f'<link rel="canonical" href="{settings.base_url}/about"' in html


def test_unknown_path_renders_noindex_404_page(client: TestClient) -> None:
    response = client.get("/does-not-exist")

    assert response.status_code == 404
    assert "That page doesn't exist." in response.text
    assert f"<title>Page not found · {settings.site_name}</title>" in response.text
    assert '<meta name="robots" content="noindex" />' in response.text
    assert 'rel="canonical"' not in response.text


def test_untrusted_host_is_rejected() -> None:
    with TestClient(app, base_url="http://evil.example") as c:
        assert c.get("/").status_code == 400


def test_healthz_responds_for_railway_healthcheck() -> None:
    # Railway probes from this host; TrustedHostMiddleware must let it through.
    with TestClient(app, base_url="http://healthcheck.railway.app") as c:
        response = c.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

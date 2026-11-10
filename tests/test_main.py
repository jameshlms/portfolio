"""Smoke tests through the real app: middleware, static mount, routers, error handlers."""

import html
import json
import re
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.paths import Page
from app.services.seo import PAGE_META, for_page
from app.templates import make_templates


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


_CURRENT_NAV_TAB = re.compile(
    r'<a class="nav-tab"\s+href="([^"]*)"\s+aria-current="page"'
)


@pytest.mark.parametrize("page", [Page.HOME, Page.ABOUT, Page.BLOG, Page.CONTACT])
def test_nav_marks_only_the_current_page(client: TestClient, page: Page) -> None:
    html = client.get(page).text

    assert _CURRENT_NAV_TAB.findall(html) == [f"http://localhost{page}"]


def test_nav_marks_no_page_on_404(client: TestClient) -> None:
    assert _CURRENT_NAV_TAB.findall(client.get("/no-such-page").text) == []


def test_contact_lists_every_way_to_reach_me(client: TestClient) -> None:
    html = client.get(Page.CONTACT).text

    assert "Get in Touch or Find More About Me" in html
    for href in (
        f"mailto:{settings.contact_email}",
        settings.linkedin_url,
        settings.github_url,
        f"http://localhost{Page.RESUME}",
        settings.gravatar_url,
    ):
        assert f'href="{href}"' in html


def test_contact_hides_gravatar_card_when_unset(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "gravatar_url", None)

    assert "Gravatar" not in client.get(Page.CONTACT).text


def test_resume_redirects_to_configured_url(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "resume_url", "https://cdn.example.com/resume.pdf")

    response = client.get(Page.RESUME, follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "https://cdn.example.com/resume.pdf"


def test_resume_falls_back_to_about_page_when_unset(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "resume_url", None)

    response = client.get(Page.RESUME, follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == f"http://localhost{Page.ABOUT}"


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
    assert "That page doesn't exist." in html.unescape(response.text)
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


@pytest.mark.parametrize("page", list(PAGE_META))
def test_pages_without_charts_do_not_load_plotly(
    client: TestClient, page: Page
) -> None:
    assert "cdn.plot.ly" not in client.get(page).text


def test_plotly_include_provides_the_script() -> None:
    html = make_templates().get_template("components/_plotly.html").render()

    assert '<script src="https://cdn.plot.ly/' in html

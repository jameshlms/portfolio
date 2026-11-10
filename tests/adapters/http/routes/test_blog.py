"""The blog through the real app, reading from the in-memory repository (conftest)."""

import asyncio
import html
import json
import re
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapters.http.paths import Page, RootFile, item_path
from app.adapters.memory_posts import InMemoryPostRepository
from app.config import settings
from tests.blog_factories import rendered

_HTMX = {"HX-Request": "true"}
_POST_PATH = item_path(Page.BLOG, "first-post")


@pytest.fixture
def client(posts: InMemoryPostRepository, app: FastAPI) -> Iterator[TestClient]:
    """The conftest app, with a few posts in its repository."""
    asyncio.run(
        posts.replace_all(
            [
                rendered(
                    "first-post",
                    title="Partitioning <large> tables",
                    tags=("sql", "postgres"),
                    revised_at=datetime(2026, 10, 20, tzinfo=UTC),
                ),
                replace(rendered("second-post", tags=("python",)), has_charts=True),
                rendered("a-draft", published_at=None, tags=("secret",)),
                rendered("scheduled", published_at=datetime(2099, 1, 1, tzinfo=UTC)),
            ]
        )
    )
    with TestClient(app, base_url="http://localhost") as c:
        yield c


def _json_ld(html: str) -> dict:
    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', html)
    assert match
    return json.loads(match.group(1))


# --- Index ---------------------------------------------------------------------


def test_index_lists_published_posts_and_their_tags(client: TestClient) -> None:
    html = client.get(Page.BLOG).text

    assert f'href="http://localhost{_POST_PATH}"' in html
    assert "Partitioning &lt;large&gt; tables" in html
    assert "second-post" in html
    for hidden in ("a-draft", "scheduled", "secret"):
        assert hidden not in html
    assert 'href="http://localhost/blog?tag=sql"' in html


def test_empty_blog_says_so(app: FastAPI) -> None:
    with TestClient(app, base_url="http://localhost") as c:
        assert "No posts yet" in c.get(Page.BLOG).text


def test_tag_filter_shows_only_tagged_posts_and_is_noindex(client: TestClient) -> None:
    response = client.get(Page.BLOG, params={"tag": "python"})

    assert response.status_code == 200
    assert "second-post" in response.text
    assert _POST_PATH not in response.text
    assert "<title>Posts tagged python · " in response.text
    assert '<meta name="robots" content="noindex" />' in response.text
    assert re.search(r'href="[^"]*\?tag=python"[^>]*aria-current="page"', response.text)


def test_htmx_tag_request_gets_the_list_fragment_with_its_title(
    client: TestClient,
) -> None:
    response = client.get(Page.BLOG, params={"tag": "sql"}, headers=_HTMX)

    assert "<html" not in response.text
    assert 'id="post-list"' in response.text
    assert "<title>Posts tagged sql · " in response.text
    assert "second-post" not in response.text


def test_history_restore_gets_the_full_page(client: TestClient) -> None:
    headers = {**_HTMX, "HX-History-Restore-Request": "true"}

    assert "<html" in client.get(Page.BLOG, params={"tag": "sql"}, headers=headers).text


@pytest.mark.parametrize("tag", ["rust", "secret"])  # unused, and only on a draft
def test_unknown_tag_is_404(client: TestClient, tag: str) -> None:
    assert client.get(Page.BLOG, params={"tag": tag}).status_code == 404


def test_empty_tag_means_no_filter(client: TestClient) -> None:
    response = client.get(Page.BLOG, params={"tag": ""})

    assert response.status_code == 200
    assert "second-post" in response.text


# --- Post ----------------------------------------------------------------------


def test_post_page_renders_the_body_and_meta(client: TestClient) -> None:
    response = client.get(_POST_PATH)

    assert response.status_code == 200
    assert "<p>Body of first-post.</p>" in response.text
    assert "<h1>Partitioning &lt;large&gt; tables</h1>" in response.text
    assert '<time datetime="2026-10-01T00:00:00+00:00">1 October 2026</time>' in (
        response.text
    )
    assert "Updated" in response.text


def test_post_head_describes_an_article(client: TestClient) -> None:
    html = client.get(_POST_PATH).text

    assert f'<link rel="canonical" href="{settings.base_url}{_POST_PATH}"' in html
    assert '<meta property="og:type" content="article" />' in html
    assert '<meta property="article:tag" content="postgres" />' in html
    nodes = {node["@type"]: node for node in _json_ld(html)["@graph"]}
    article = nodes["BlogPosting"]
    assert article["headline"] == "Partitioning <large> tables"
    assert article["dateModified"] == "2026-10-20T00:00:00Z"
    assert article["keywords"] == ["sql", "postgres"]
    crumbs = [i["name"] for i in nodes["BreadcrumbList"]["itemListElement"]]
    assert crumbs == ["Home", "Blog", "Partitioning <large> tables"]


def test_only_posts_with_charts_load_plotly(client: TestClient) -> None:
    assert "cdn.plot.ly" in client.get(item_path(Page.BLOG, "second-post")).text
    assert "cdn.plot.ly" not in client.get(_POST_PATH).text
    assert "cdn.plot.ly" not in client.get(Page.BLOG).text


@pytest.mark.parametrize("slug", ["nope", "a-draft", "scheduled"])
def test_unpublished_posts_are_404(client: TestClient, slug: str) -> None:
    response = client.get(item_path(Page.BLOG, slug))

    assert response.status_code == 404
    assert "That page doesn't exist." in html.unescape(response.text)


# --- Crawler files -------------------------------------------------------------


def test_sitemap_lists_published_posts_with_lastmod(client: TestClient) -> None:
    xml = client.get(RootFile.SITEMAP).text

    assert (
        f"<loc>{settings.base_url}{_POST_PATH}</loc>\n    <lastmod>2026-10-20</lastmod>"
        in xml
    )
    assert "a-draft" not in xml
    assert "scheduled" not in xml


def test_llms_txt_has_a_blog_section(client: TestClient) -> None:
    text = client.get(RootFile.LLMS).text

    assert "## Blog" in text
    assert f"({settings.base_url}{_POST_PATH}): Summary of first-post." in text

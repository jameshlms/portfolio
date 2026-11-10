"""Errors through the real app: domain errors, HTTP errors, validation, crashes."""

import html
import inspect
import re
from collections.abc import AsyncIterator, Iterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapters.http.app import create_app
from app.adapters.http.exception_handlers import status_for
from app.adapters.http.paths import Page, RootFile, item_path
from app.container import Container
from app.domain import errors
from app.domain.blog import Post, PostSummary, RenderedPost
from app.domain.errors import DomainError, InvalidPosts, PostsUnavailable
from app.ports.driven.blog import PostRepository

_HTMX = {"HX-Request": "true"}


class BrokenRepository:
    """A PostRepository whose store is unreachable, or that raises `error`."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error or PostsUnavailable("down")

    async def published(self, as_of: datetime) -> tuple[PostSummary, ...]:
        raise self.error

    async def get_published(self, slug: str, as_of: datetime) -> Post | None:
        raise self.error

    async def replace_all(self, posts: Sequence[RenderedPost]) -> tuple[str, ...]:
        raise self.error


def _client(container: Container, error: Exception | None = None) -> TestClient:
    repository = BrokenRepository(error)

    @asynccontextmanager
    async def scope() -> AsyncIterator[PostRepository]:
        yield repository

    # Unexpected errors are re-raised by default; check the response instead.
    return TestClient(
        create_app(replace(container, posts=scope)),
        base_url="http://localhost",
        raise_server_exceptions=False,
    )


@pytest.fixture
def down(container: Container) -> Iterator[TestClient]:
    with _client(container) as c:
        yield c


def _text(response_text: str) -> str:
    return html.unescape(response_text)


# --- Domain errors -------------------------------------------------------------


@pytest.mark.parametrize(
    "path", [Page.BLOG, item_path(Page.BLOG, "a-post"), RootFile.SITEMAP, RootFile.LLMS]
)
def test_unreachable_posts_give_a_503_error_page(down: TestClient, path: str) -> None:
    response = down.get(path)

    assert response.status_code == 503
    assert "<html" in response.text
    assert "can't load right now" in _text(response.text)
    assert '<meta name="robots" content="noindex" />' in response.text


def test_other_pages_still_work_when_posts_are_unreachable(down: TestClient) -> None:
    assert down.get(Page.ABOUT).status_code == 200


def test_htmx_errors_replace_main_instead_of_the_small_target(down: TestClient) -> None:
    response = down.get(Page.BLOG, params={"tag": "python"}, headers=_HTMX)

    assert response.status_code == 503
    assert "<html" not in response.text
    assert re.search(r'<main id="main-content">', response.text)
    assert response.headers["HX-Retarget"] == "#main-content"
    assert response.headers["HX-Reswap"] == "outerHTML"
    assert "<title>Temporarily unavailable · " in response.text


def test_htmx_history_restore_gets_the_full_error_page(down: TestClient) -> None:
    headers = {**_HTMX, "HX-History-Restore-Request": "true"}

    response = down.get(Page.BLOG, headers=headers)

    assert "<html" in response.text
    assert "HX-Retarget" not in response.headers


def test_unknown_tag_over_htmx_is_a_retargeted_404(client: TestClient) -> None:
    response = client.get(Page.BLOG, params={"tag": "nope"}, headers=_HTMX)

    assert response.status_code == 404
    assert response.headers["HX-Retarget"] == "#main-content"
    assert "That page doesn't exist." in _text(response.text)


def test_unmapped_domain_error_is_a_500(container: Container) -> None:
    with _client(container, InvalidPosts([])) as c:
        response = c.get(Page.BLOG)

    assert response.status_code == 500
    assert "Something went wrong on my end." in response.text


def test_api_paths_get_json(down: TestClient) -> None:
    response = down.get("/api/nothing-here")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


# Raised only by the sync CLI, or abstract bases: never meant to reach a request.
_NOT_FOR_HTTP = {
    "DomainError",
    "ContactError",
    "BlogError",
    "InvalidPost",
    "InvalidPosts",
}


@pytest.mark.parametrize(
    "cls",
    [
        c
        for _, c in inspect.getmembers(errors, inspect.isclass)
        if issubclass(c, DomainError) and c.__name__ not in _NOT_FOR_HTTP
    ],
    ids=lambda c: c.__name__,
)
def test_every_request_facing_domain_error_has_a_status(cls: type[DomainError]) -> None:
    instance = cls.__new__(cls)  # constructors differ; only the type matters here

    assert status_for(instance) is not None, f"Map {cls.__name__} in _DOMAIN_STATUS"


# --- Validation and crashes ----------------------------------------------------


def _app_with(container: Container) -> FastAPI:
    app = create_app(container)

    @app.get("/needs-a-number")
    async def needs_a_number(n: int) -> dict[str, int]:
        return {"n": n}

    @app.get("/api/needs-a-number")
    async def api_needs_a_number(n: int) -> dict[str, int]:
        return {"n": n}

    @app.get("/crashes")
    async def crashes() -> None:
        raise RuntimeError("bug")

    return app


@pytest.fixture
def extra(container: Container) -> Iterator[TestClient]:
    with TestClient(
        _app_with(container), base_url="http://localhost", raise_server_exceptions=False
    ) as c:
        yield c


def test_invalid_input_gets_a_422_page_not_json(extra: TestClient) -> None:
    response = extra.get("/needs-a-number", params={"n": "seven"})

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("text/html")
    assert "wasn't valid" in _text(response.text)


def test_invalid_input_under_api_gets_json(extra: TestClient) -> None:
    response = extra.get("/api/needs-a-number", params={"n": "seven"})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", "n"]


def test_unexpected_exception_gets_the_500_page(extra: TestClient) -> None:
    response = extra.get("/crashes")

    assert response.status_code == 500
    assert "Something went wrong on my end." in response.text
    assert "<html" in response.text

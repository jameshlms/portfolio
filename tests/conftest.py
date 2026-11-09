import os

# Placeholders so tests never use a developer's .env (environment variables win
# over .env). Nothing in the tests connects to DATABASE_URL: app tests run on a
# Container of fakes, and the Postgres tests use TEST_DATABASE_URL.
_REQUIRED_SETTINGS = {
    "GITHUB_TOKEN": "test",
    "GITHUB_CLIENT_ID": "test",
    "GITHUB_CLIENT_SECRET": "test",
    "GITHUB_ADMIN_USERNAME": "test",
    "SESSION_SECRET_KEY": "test",
    "DATABASE_URL": "postgresql://test:test@localhost/test",
    "REDIS_URL": "redis://localhost",
}
for key, value in _REQUIRED_SETTINGS.items():
    os.environ.setdefault(key, value)


# Imported after the settings above are in place.
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapters.http.app import create_app
from app.adapters.markdown import MarkdownItRenderer
from app.adapters.memory_posts import InMemoryPostRepository, memory_post_repositories
from app.container import Container


@pytest.fixture
def anyio_backend() -> str:
    """Run @pytest.mark.anyio tests on asyncio only (anyio's plugin also tries trio)."""
    return "asyncio"


@pytest.fixture
def posts() -> InMemoryPostRepository:
    """The blog's repository: empty unless a test adds posts."""
    return InMemoryPostRepository()


@pytest.fixture
def container(posts: InMemoryPostRepository) -> Container:
    """Fakes for every port; the contact form is off (no verifier or sender)."""
    return Container(
        posts=memory_post_repositories(posts), renderer=MarkdownItRenderer()
    )


@pytest.fixture
def app(container: Container) -> FastAPI:
    """A fresh app per test, so no state (rate limits, overrides) leaks between tests."""
    return create_app(container)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    # TrustedHostMiddleware rejects TestClient's default "testserver" host.
    with TestClient(app, base_url="http://localhost") as c:
        yield c

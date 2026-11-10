import os

# A placeholder so tests never pick up a developer's .env DATABASE_URL (environment
# variables win over .env). No app test connects to it: the blog's repository is
# overridden below, and the Postgres tests use TEST_DATABASE_URL.
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")


# Imported after the settings above are in place.
from collections.abc import Iterator

import pytest

from app.adapters.memory_posts import InMemoryPostRepository
from app.deps.blog import get_post_repository
from app.main import app


@pytest.fixture
def anyio_backend() -> str:
    """Run @pytest.mark.anyio tests on asyncio only (anyio's plugin also tries trio)."""
    return "asyncio"


@pytest.fixture(autouse=True)
def posts() -> Iterator[InMemoryPostRepository]:
    """The blog's repository for every app test: empty unless a test adds posts.

    The DATABASE_URL above is a placeholder, so no test may reach Postgres
    through the app.
    """
    repository = InMemoryPostRepository()
    app.dependency_overrides[get_post_repository] = lambda: repository
    yield repository
    app.dependency_overrides.pop(get_post_repository, None)

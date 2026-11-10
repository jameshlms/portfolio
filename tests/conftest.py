import os

# Before the app is imported: its settings must not read a developer's .env, so the
# tests run the same everywhere (see app/config.py). Environment variables still apply.
os.environ["PORTFOLIO_ENV_FILE"] = ""


# Imported after PORTFOLIO_ENV_FILE is in place.
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

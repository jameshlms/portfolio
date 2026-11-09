import os

# Settings() is built at import time and these have no defaults; set placeholders
# so tests don't depend on a local .env. Real values in the environment win.
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

from collections.abc import Callable
from dataclasses import replace

import pytest

from app import paths
from app.services.seo import page_meta


@pytest.fixture
def noindex(monkeypatch: pytest.MonkeyPatch) -> Callable[[paths.Page], None]:
    """Mark a page noindex for one test; every SEO module reads page_meta.PAGE_META."""

    def mark(page: paths.Page) -> None:
        meta = dict(page_meta.PAGE_META)
        meta[page] = replace(meta[page], noindex=True)
        monkeypatch.setattr(page_meta, "PAGE_META", meta)

    return mark

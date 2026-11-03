from collections.abc import Callable
from datetime import UTC, datetime

from app import paths
from app.config import settings
from app.services.seo.llms import llms_document
from app.services.seo.page_meta import PAGE_META, PublishedPage

UPDATED = datetime(2026, 10, 1, 12, 30, tzinfo=UTC)


def test_llms_document_sections_and_absolute_urls() -> None:
    doc = llms_document(
        [PublishedPage("/blog/first", "First post", "Why I built this.", UPDATED)]
    )

    assert doc.title == settings.site_name
    assert doc.summary == PAGE_META[paths.Page.HOME].description
    assert [s.heading for s in doc.sections] == ["Pages", "Blog", "Optional"]

    pages, blog, _ = doc.sections
    # Home is the H1, so it isn't repeated as a link.
    assert f"{settings.base_url}/" not in {link.url for link in pages.links}
    assert blog.links[0].url == f"{settings.base_url}/blog/first"
    assert blog.links[0].notes == "Why I built this."


def test_llms_document_omits_empty_blog_section() -> None:
    assert "Blog" not in [s.heading for s in llms_document([]).sections]


def test_llms_document_excludes_noindex_pages(
    noindex: Callable[[paths.Page], None],
) -> None:
    noindex(paths.Page.CONTACT)

    titles = {link.title for link in llms_document([]).sections[0].links}

    assert PAGE_META[paths.Page.CONTACT].title not in titles

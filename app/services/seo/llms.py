"""llms.txt document (https://llmstxt.org)."""

from collections.abc import Iterable
from dataclasses import dataclass

from app import paths
from app.config import settings
from app.services.seo import page_meta
from app.services.seo.page_meta import PublishedPage
from app.services.seo.urls import absolute_url


@dataclass(frozen=True)
class LlmsLink:
    title: str
    url: str
    notes: str = ""


@dataclass(frozen=True)
class LlmsSection:
    heading: str
    links: tuple[LlmsLink, ...]


@dataclass(frozen=True)
class LlmsDocument:
    title: str
    summary: str
    sections: tuple[LlmsSection, ...]


def llms_document(posts: Iterable[PublishedPage]) -> LlmsDocument:
    pages = LlmsSection(
        "Pages",
        tuple(
            LlmsLink(meta.title, absolute_url(page), meta.description)
            for page, meta in page_meta.PAGE_META.items()
            if not meta.noindex and page != paths.Page.HOME
        ),
    )
    blog = LlmsSection(
        "Blog",
        tuple(LlmsLink(p.title, absolute_url(p.path), p.summary) for p in posts),
    )
    # "Optional" is a reserved heading in the spec: links an LLM may skip for brevity.
    elsewhere = LlmsSection(
        "Optional",
        (
            LlmsLink("GitHub", settings.github_url),
            LlmsLink("LinkedIn", settings.linkedin_url),
        ),
    )

    return LlmsDocument(
        title=settings.site_name,
        summary=page_meta.PAGE_META[paths.Page.HOME].description,
        sections=tuple(s for s in (pages, blog, elsewhere) if s.links),
    )

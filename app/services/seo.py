from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from itertools import chain
from typing import Any

from app import paths
from app.config import settings


def _abs_url(path: str) -> str:
    return f"{settings.base_url}/{path.removeprefix("/")}"


def _abs_media_url(url: str) -> str:
    """Media may live on another host (CDN); only site-relative paths are resolved."""
    return url if "://" in url else _abs_url(url)

PERSON_ID = _abs_url("/#person")
SITE_ID = _abs_url("/#website")


@dataclass
class SEOContext:
    title: str
    description: str
    path: str                          # canonical path, no query string
    og_image: str | None = None
    og_image_alt: str | None = None
    og_type: str = "website"
    og_locale: str = "en_US"
    noindex: bool = False
    published: datetime | None = None
    modified: datetime | None = None
    jsonld: list[dict] = field(default_factory=list)   # nodes for one @graph

    @property
    def canonical(self) -> str: return _abs_url(self.path)

    @property
    def full_title(self) -> str:
        return self.title if self.path == paths.Page.HOME else f"{self.title} - {settings.site_name}"

@dataclass(frozen=True)
class SitemapEntry:
    loc: str
    lastmod: datetime | None = None
    images: tuple[str, ...] = ()    # image sitemap ext.


@dataclass(frozen=True)
class StaticPage:
    title: str
    description: str
    jsonld_type: str = "WebPage"
    noindex: bool = False


# Only pages with a registered route belong here: this drives the sitemap and llms.txt.
# Add RESUME / PROJECTS ("CollectionPage") / BLOG ("CollectionPage") as their routes ship.
STATIC_PAGES: dict[paths.Page, StaticPage] = {   # placeholder copy: write your own
    paths.Page.HOME:     StaticPage("Data engineer building ML systems", "Pipelines, platforms and ML systems by James."),
    paths.Page.ABOUT:    StaticPage("About", "Background, skills and how I work.", "ProfilePage"),
    paths.Page.CONTACT:  StaticPage("Contact", "Get in touch.", "ContactPage"),
}

def _website_ld() -> dict[str, Any]: ...
def _person_ld(p) -> dict[str, Any]: ...
def _page_ld(sp: StaticPage, path: str) -> dict[str, Any]: ...
def _breadcrumb_ld(crumbs: Iterable[tuple[str, str]]) -> dict[str, Any]: ...
def _project_ld() -> dict[str, Any]: ...
def _post_ld() -> dict[str, Any]: ...

def for_static(page: paths.Page, profile) -> SEOContext:
    sp = STATIC_PAGES[page]
    nodes = [
        _website_ld(),
        _person_ld(profile),
        _page_ld(sp, page)
    ]

    if page != paths.Page.HOME:
        nodes.append(_breadcrumb_ld([("Home", paths.Page.HOME), (sp.title, page)]))

    return SEOContext(
        title=sp.title,
        description=sp.description,
        path=page,
        noindex=sp.noindex,
        jsonld=nodes
    )

def for_project(project, profile) -> SEOContext:
    path = paths.project(project.slug)
    return SEOContext(
        title=project.seo_title or project.title,
        description=project.summary,
        path=path,
        og_type="article",  # long-form case study; use "website" if you prefer
        og_image=project.cover.og_url if project.cover else None,
        og_image_alt=project.cover.alt if project.cover else None,
        published=project.published_at,
        modified=project.updated_at,
        author_url=_abs_url(paths.Page.ABOUT),
        tags=[t.name for t in project.tags],
        jsonld=[
            _website_ld(),
            _person_ld(profile),
            _project_ld(project),
            _breadcrumb_ld(
                [
                    ("Home", paths.Page.HOME),
                    ("Projects", paths.Page.PROJECTS),
                    (project.title, path)
                ]
            ),
        ],
    )


@dataclass(frozen=True)
class Media:
    url: str                           # site-relative path or absolute URL


@dataclass(frozen=True)
class EntityDetails:
    path: str                          # site-relative, e.g. "/blog/my-post"
    updated_at: datetime
    media: tuple[Media, ...] = ()


def sitemap_entries(*entity_listings: Iterable[EntityDetails]) -> tuple[SitemapEntry, ...]:
    static_pages = (
        SitemapEntry(_abs_url(page))
        for page, sp in STATIC_PAGES.items()
        if not sp.noindex
    )
    dynamic_pages = (
        SitemapEntry(
            _abs_url(e.path),
            e.updated_at,
            tuple(_abs_media_url(m.url) for m in e.media),
        )
        for e in chain.from_iterable(entity_listings)
    )

    return (*static_pages, *dynamic_pages)


@dataclass(frozen=True)
class Listing:
    path: str                          # site-relative, e.g. "/blog/my-post"
    title: str
    summary: str


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


def llms_document(posts: Iterable[Listing]) -> LlmsDocument:
    """Content for /llms.txt, following https://llmstxt.org."""
    pages = LlmsSection(
        "Pages",
        tuple(
            LlmsLink(sp.title, _abs_url(page), sp.description)
            for page, sp in STATIC_PAGES.items()
            if not sp.noindex and page != paths.Page.HOME
        ),
    )
    blog = LlmsSection(
        "Blog",
        tuple(LlmsLink(p.title, _abs_url(p.path), p.summary) for p in posts),
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
        summary=STATIC_PAGES[paths.Page.HOME].description,
        sections=tuple(s for s in (pages, blog, elsewhere) if s.links),
    )

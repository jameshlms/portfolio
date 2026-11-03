from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from itertools import chain
from typing import Any

from app import paths
from app.config import settings

TITLE_SEPARATOR = " · "
LANGUAGE = "en"


def absolute_url(path: str) -> str:
    return f"{settings.base_url}/{path.removeprefix('/')}"


def _absolute_asset_url(url: str) -> str:
    """Assets may live on another host (CDN); only site-relative paths are resolved."""
    return url if "://" in url else absolute_url(url)


# schema.org @id values: stable node identifiers shared across every page's @graph.
PERSON_ID = absolute_url("/#person")
WEBSITE_ID = absolute_url("/#website")
_PROFILE_IMAGE = f"{paths.Internal.STATIC}/images/pfp.jpg"


# --- Page metadata -----------------------------------------------------------


@dataclass(frozen=True)
class PageMeta:
    title: str
    description: str
    schema_type: str = "WebPage"  # schema.org @type of the page node
    noindex: bool = False


# Only pages with a registered route belong here: this drives the sitemap and llms.txt.
# Add RESUME / PROJECTS ("CollectionPage") / BLOG ("CollectionPage") as their routes ship.
# fmt: off
PAGE_META: dict[paths.Page, PageMeta] = {   # placeholder copy: write your own
    paths.Page.HOME:     PageMeta("Data engineer building ML systems", "Pipelines, platforms and ML systems by James."),
    paths.Page.ABOUT:    PageMeta("About", "Background, skills and how I work.", "ProfilePage"),
    paths.Page.CONTACT:  PageMeta("Contact", "Get in touch.", "ContactPage"),
}
# fmt: on


@dataclass(frozen=True)
class PublishedPage:
    """A published item page (blog post, project) as crawlers should see it."""

    path: str  # site-relative, e.g. "/blog/my-post"
    title: str
    summary: str
    last_modified: datetime
    images: tuple[str, ...] = ()  # site-relative paths or absolute URLs


# --- <head> metadata ---------------------------------------------------------


@dataclass(frozen=True)
class SEOContext:
    """Everything base.html renders into <head>: title, meta, Open Graph, JSON-LD."""

    title: str  # page title alone; also og:title
    description: str
    path: str  # canonical path, no query string
    og_image: str | None = None
    og_image_alt: str | None = None
    og_type: str = "website"
    og_locale: str = "en_US"
    noindex: bool = False
    date_published: datetime | None = None
    date_modified: datetime | None = None
    author_url: str | None = None  # article:author
    tags: tuple[str, ...] = ()  # article:tag
    structured_data: tuple[dict[str, Any], ...] = ()  # schema.org nodes for one @graph

    @property
    def canonical(self) -> str:
        return absolute_url(self.path)

    @property
    def document_title(self) -> str:
        """The <title>: brand first on the home page, last everywhere else."""
        if self.path == paths.Page.HOME:
            return f"{settings.site_name}{TITLE_SEPARATOR}{self.title}"
        return f"{self.title}{TITLE_SEPARATOR}{settings.site_name}"

    @property
    def json_ld(self) -> dict[str, Any]:
        return {"@context": "https://schema.org", "@graph": list(self.structured_data)}


def _website_node() -> dict[str, Any]:
    return {
        "@type": "WebSite",
        "@id": WEBSITE_ID,
        "url": absolute_url(paths.Page.HOME),
        "name": settings.site_name,
        "inLanguage": LANGUAGE,
        "publisher": {"@id": PERSON_ID},
    }


def _person_node() -> dict[str, Any]:
    return {
        "@type": "Person",
        "@id": PERSON_ID,
        "name": settings.site_name,
        "url": absolute_url(paths.Page.HOME),
        "image": absolute_url(_PROFILE_IMAGE),
        "sameAs": [settings.github_url, settings.linkedin_url],
    }


def _webpage_node(meta: PageMeta, path: str) -> dict[str, Any]:
    url = absolute_url(path)
    node: dict[str, Any] = {
        "@type": meta.schema_type,
        "@id": f"{url}#webpage",
        "url": url,
        "name": meta.title,
        "description": meta.description,
        "inLanguage": LANGUAGE,
        "isPartOf": {"@id": WEBSITE_ID},
    }
    if meta.schema_type == "ProfilePage":
        node["mainEntity"] = {"@id": PERSON_ID}
    return node


def _breadcrumb_node(crumbs: Iterable[tuple[str, str]]) -> dict[str, Any]:
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": position,
                "name": name,
                "item": absolute_url(path),
            }
            for position, (name, path) in enumerate(crumbs, start=1)
        ],
    }


def _project_node(project: Any, path: str) -> dict[str, Any]:
    url = absolute_url(path)
    return {
        "@type": "CreativeWork",
        "@id": f"{url}#project",
        "url": url,
        "name": project.title,
        "description": project.summary,
        "author": {"@id": PERSON_ID},
        "datePublished": project.published_at.isoformat(),
        "dateModified": project.updated_at.isoformat(),
    }


def for_page(page: paths.Page) -> SEOContext:
    meta = PAGE_META[page]
    nodes = [_website_node(), _person_node(), _webpage_node(meta, page)]

    if page != paths.Page.HOME:
        nodes.append(_breadcrumb_node([("Home", paths.Page.HOME), (meta.title, page)]))

    return SEOContext(
        title=meta.title,
        description=meta.description,
        path=page,
        noindex=meta.noindex,
        structured_data=tuple(nodes),
    )


def for_error_page(title: str, description: str, path: str) -> SEOContext:
    return SEOContext(title=title, description=description, path=path, noindex=True)


# `project` is duck-typed until the Project model exists.
def for_project(project: Any) -> SEOContext:
    path = paths.item_path(paths.Page.PROJECTS, project.slug)
    return SEOContext(
        title=project.seo_title or project.title,
        description=project.summary,
        path=path,
        og_type="article",  # long-form case study; use "website" if you prefer
        og_image=project.cover.og_url if project.cover else None,
        og_image_alt=project.cover.alt if project.cover else None,
        date_published=project.published_at,
        date_modified=project.updated_at,
        author_url=absolute_url(paths.Page.ABOUT),
        tags=tuple(t.name for t in project.tags),
        structured_data=(
            _website_node(),
            _person_node(),
            _project_node(project, path),
            _breadcrumb_node(
                [
                    ("Home", paths.Page.HOME),
                    ("Projects", paths.Page.PROJECTS),
                    (project.title, path),
                ]
            ),
        ),
    )


# --- sitemap.xml -------------------------------------------------------------


@dataclass(frozen=True)
class SitemapUrl:
    """One <url> element; field names follow the sitemaps.org protocol."""

    loc: str
    lastmod: datetime | None = None
    images: tuple[str, ...] = ()  # <image:image> extension


def sitemap_urls(*collections: Iterable[PublishedPage]) -> tuple[SitemapUrl, ...]:
    pages = (
        SitemapUrl(absolute_url(page))
        for page, meta in PAGE_META.items()
        if not meta.noindex
    )
    items = (
        SitemapUrl(
            absolute_url(item.path),
            item.last_modified,
            tuple(_absolute_asset_url(img) for img in item.images),
        )
        for item in chain.from_iterable(collections)
    )

    return (*pages, *items)


# --- llms.txt (https://llmstxt.org) ------------------------------------------


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
            for page, meta in PAGE_META.items()
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
        summary=PAGE_META[paths.Page.HOME].description,
        sections=tuple(s for s in (pages, blog, elsewhere) if s.links),
    )

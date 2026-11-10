from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from itertools import chain
from typing import Any, Literal

from app import paths
from app.config import settings
from app.services.blog import Post, PostSummary
from app.services.open_graph import MetaProperty, OpenGraph, OpenGraphArticle
from app.services.schema_org import (
    BlogPosting,
    BreadcrumbList,
    GraphNode,
    JsonLdDocument,
    ListItem,
    PageType,
    Person,
    Ref,
    WebPage,
    WebSite,
)

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
    schema_type: PageType = "WebPage"  # schema.org @type of the page node
    noindex: bool = False


# Only pages with a registered route belong here: this drives the sitemap and llms.txt.
# Add RESUME as its route ships.
# fmt: off
PAGE_META: dict[paths.Page, PageMeta] = {   # placeholder copy: write your own
    paths.Page.HOME:     PageMeta("Data engineer building ML systems", "Pipelines, platforms and ML systems by James."),
    paths.Page.ABOUT:    PageMeta("About", "Background, skills and how I work.", "ProfilePage"),
    paths.Page.BLOG:     PageMeta("Blog", "Notes on data engineering, ML systems and the tools behind them.", "CollectionPage"),
    paths.Page.CONTACT:  PageMeta("Contact", "Get in touch about roles, projects and collaborations.", "ContactPage"),
}
# fmt: on


@dataclass(frozen=True)
class PublishedPage:
    """A published item page (e.g. a blog post) as crawlers should see it."""

    path: str  # site-relative, e.g. "/blog/my-post"
    title: str
    summary: str
    last_modified: datetime
    images: tuple[str, ...] = ()  # site-relative paths or absolute URLs


@dataclass(frozen=True)
class Crumb:
    """One step of a breadcrumb trail."""

    name: str
    path: str


@dataclass(frozen=True)
class SocialImage:
    """The preview image shown when a page is shared."""

    url: str  # absolute
    alt: str
    width: (
        int  # pixels; sent as og:image:width/height so previews lay out without a fetch
    )
    height: int

    @property
    def is_wide(self) -> bool:
        """Wide enough for a large preview card (1200x630, the usual size, is ~1.91:1)."""
        return self.width >= 1.9 * self.height


# Used wherever a page has no image of its own. Swap for a 1200x630 image for large cards.
DEFAULT_SOCIAL_IMAGE = SocialImage(
    url=absolute_url(_PROFILE_IMAGE),
    alt=f"Profile picture of {settings.site_name}",
    width=868,
    height=868,
)


# --- <head> metadata ---------------------------------------------------------


@dataclass(frozen=True)
class SEOContext:
    """Facts about a page; base.html renders <head> from what they derive."""

    title: str  # page title alone; also og:title
    description: str
    path: str  # canonical path, no query string
    noindex: bool = False
    image: SocialImage | None = DEFAULT_SOCIAL_IMAGE
    article: OpenGraphArticle | None = None  # set for long-form pages (og:type=article)
    structured_data: tuple[GraphNode, ...] = ()  # schema.org nodes for one @graph

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
    def open_graph(self) -> OpenGraph:
        return OpenGraph(
            type="article" if self.article else "website",
            title=self.title,
            description=self.description,
            url=None if self.noindex else self.canonical,
            site_name=settings.site_name,
            image=self.image.url if self.image else None,
            image_width=self.image.width if self.image else None,
            image_height=self.image.height if self.image else None,
            image_alt=self.image.alt if self.image else None,
        )

    @property
    def meta_properties(self) -> tuple[MetaProperty, ...]:
        """Every <meta property="..."> tag: Open Graph, then article:* if any."""
        article = self.article.meta_properties() if self.article else ()
        return (*self.open_graph.meta_properties(), *article)

    @property
    def twitter_card(self) -> Literal["summary", "summary_large_image"]:
        return "summary_large_image" if self.image and self.image.is_wide else "summary"

    @property
    def json_ld(self) -> dict[str, Any]:
        return JsonLdDocument(graph=self.structured_data).to_json_ld()


def _website_node() -> WebSite:
    return WebSite(
        id=WEBSITE_ID,
        url=absolute_url(paths.Page.HOME),
        name=settings.site_name,
        in_language=LANGUAGE,
        publisher=Ref(id=PERSON_ID),
    )


def _person_node() -> Person:
    return Person(
        id=PERSON_ID,
        name=settings.site_name,
        url=absolute_url(paths.Page.HOME),
        image=absolute_url(_PROFILE_IMAGE),
        same_as=(settings.github_url, settings.linkedin_url),
    )


def _webpage_node(meta: PageMeta, path: str) -> WebPage:
    url = absolute_url(path)
    return WebPage(
        type=meta.schema_type,
        id=f"{url}#webpage",
        url=url,
        name=meta.title,
        description=meta.description,
        in_language=LANGUAGE,
        is_part_of=Ref(id=WEBSITE_ID),
        main_entity=Ref(id=PERSON_ID) if meta.schema_type == "ProfilePage" else None,
    )


def _breadcrumb_node(crumbs: Iterable[Crumb]) -> BreadcrumbList:
    return BreadcrumbList(
        item_list_element=tuple(
            ListItem(position=position, name=crumb.name, item=absolute_url(crumb.path))
            for position, crumb in enumerate(crumbs, start=1)
        )
    )


_HOME_CRUMB = Crumb("Home", paths.Page.HOME)


def for_page(page: paths.Page) -> SEOContext:
    meta = PAGE_META[page]
    nodes: list[GraphNode] = [
        _website_node(),
        _person_node(),
        _webpage_node(meta, page),
    ]

    if page != paths.Page.HOME:
        nodes.append(_breadcrumb_node([_HOME_CRUMB, Crumb(meta.title, page)]))

    return SEOContext(
        title=meta.title,
        description=meta.description,
        path=page,
        noindex=meta.noindex,
        structured_data=tuple(nodes),
    )


def for_error_page(title: str, description: str, path: str) -> SEOContext:
    return SEOContext(title=title, description=description, path=path, noindex=True)


def for_blog_index(tag: str | None = None) -> SEOContext:
    """The blog index; a tag-filtered view is noindex, as it repeats the index's posts."""
    page = for_page(paths.Page.BLOG)
    if tag is None:
        return page
    return SEOContext(
        title=f"Posts tagged {tag}",
        description=f"Blog posts about {tag}.",
        path=paths.Page.BLOG,
        noindex=True,
    )


def _blog_posting_node(post: Post, url: str) -> BlogPosting:
    return BlogPosting(
        id=f"{url}#article",
        url=url,
        name=post.title,
        headline=post.title,
        description=post.summary,
        in_language=LANGUAGE,
        author=Ref(id=PERSON_ID),
        publisher=Ref(id=PERSON_ID),
        is_part_of=Ref(id=WEBSITE_ID),
        main_entity_of_page=url,
        date_published=post.published_at,
        date_modified=post.last_modified,
        keywords=post.tags or None,
    )


def for_post(post: Post) -> SEOContext:
    path = paths.item_path(paths.Page.BLOG, post.slug)
    return SEOContext(
        title=post.title,
        description=post.summary,
        path=path,
        article=OpenGraphArticle(
            published_time=post.published_at,
            modified_time=post.last_modified,
            author=absolute_url(paths.Page.ABOUT),
            tags=post.tags,
        ),
        structured_data=(
            _website_node(),
            _person_node(),
            _blog_posting_node(post, absolute_url(path)),
            _breadcrumb_node(
                [
                    _HOME_CRUMB,
                    Crumb(PAGE_META[paths.Page.BLOG].title, paths.Page.BLOG),
                    Crumb(post.title, path),
                ]
            ),
        ),
    )


def published_posts(posts: Iterable[PostSummary]) -> tuple[PublishedPage, ...]:
    """Blog posts as the sitemap and llms.txt list them."""
    return tuple(
        PublishedPage(
            path=paths.item_path(paths.Page.BLOG, post.slug),
            title=post.title,
            summary=post.summary,
            last_modified=post.last_modified,
        )
        for post in posts
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

"""SEOContext: the facts base.html renders into <head>, built per page."""

from dataclasses import dataclass
from typing import Any, Literal

from app import paths
from app.config import settings
from app.services.seo import page_meta
from app.services.seo.open_graph import MetaProperty, OpenGraph, OpenGraphArticle
from app.services.seo.schema_org import GraphNode, JsonLdDocument
from app.services.seo.structured_data import (
    HOME_CRUMB,
    Crumb,
    breadcrumb_node,
    person_node,
    project_node,
    webpage_node,
    website_node,
)
from app.services.seo.urls import absolute_url

TITLE_SEPARATOR = " · "


@dataclass(frozen=True)
class SocialImage:
    """The preview image shown when a page is shared."""

    url: str  # absolute
    alt: str


@dataclass(frozen=True)
class SEOContext:
    """Facts about a page; base.html renders <head> from what they derive."""

    title: str  # page title alone; also og:title
    description: str
    path: str  # canonical path, no query string
    noindex: bool = False
    image: SocialImage | None = None
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
            image_alt=self.image.alt if self.image else None,
        )

    @property
    def meta_properties(self) -> tuple[MetaProperty, ...]:
        """Every <meta property="..."> tag: Open Graph, then article:* if any."""
        article = self.article.meta_properties() if self.article else ()
        return (*self.open_graph.meta_properties(), *article)

    @property
    def twitter_card(self) -> Literal["summary", "summary_large_image"]:
        return "summary_large_image" if self.image else "summary"

    @property
    def json_ld(self) -> dict[str, Any]:
        return JsonLdDocument(graph=self.structured_data).to_json_ld()


def for_page(page: paths.Page) -> SEOContext:
    meta = page_meta.PAGE_META[page]
    nodes: list[GraphNode] = [website_node(), person_node(), webpage_node(meta, page)]

    if page != paths.Page.HOME:
        nodes.append(breadcrumb_node([HOME_CRUMB, Crumb(meta.title, page)]))

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
        image=SocialImage(project.cover.og_url, project.cover.alt)
        if project.cover
        else None,
        article=OpenGraphArticle(  # long-form case study; drop for og:type=website
            published_time=project.published_at,
            modified_time=project.updated_at,
            author=absolute_url(paths.Page.ABOUT),
            tags=tuple(t.name for t in project.tags),
        ),
        structured_data=(
            website_node(),
            person_node(),
            project_node(project, path),
            breadcrumb_node(
                [
                    HOME_CRUMB,
                    Crumb("Projects", paths.Page.PROJECTS),
                    Crumb(project.title, path),
                ]
            ),
        ),
    )

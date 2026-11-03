"""This site's schema.org nodes, linked into one graph by stable @id values."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from app import paths
from app.config import settings
from app.services.seo.page_meta import PageMeta
from app.services.seo.schema_org import (
    BreadcrumbList,
    CreativeWork,
    ListItem,
    Person,
    Ref,
    WebPage,
    WebSite,
)
from app.services.seo.urls import absolute_url

LANGUAGE = "en"

# schema.org @id values: stable node identifiers shared across every page's @graph.
PERSON_ID = absolute_url("/#person")
WEBSITE_ID = absolute_url("/#website")
_PROFILE_IMAGE = f"{paths.Internal.STATIC}/images/pfp.jpg"


@dataclass(frozen=True)
class Crumb:
    """One step of a breadcrumb trail."""

    name: str
    path: str


HOME_CRUMB = Crumb("Home", paths.Page.HOME)


def website_node() -> WebSite:
    return WebSite(
        id=WEBSITE_ID,
        url=absolute_url(paths.Page.HOME),
        name=settings.site_name,
        in_language=LANGUAGE,
        publisher=Ref(id=PERSON_ID),
    )


def person_node() -> Person:
    return Person(
        id=PERSON_ID,
        name=settings.site_name,
        url=absolute_url(paths.Page.HOME),
        image=absolute_url(_PROFILE_IMAGE),
        same_as=(settings.github_url, settings.linkedin_url),
    )


def webpage_node(meta: PageMeta, path: str) -> WebPage:
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


def breadcrumb_node(crumbs: Iterable[Crumb]) -> BreadcrumbList:
    return BreadcrumbList(
        item_list_element=tuple(
            ListItem(position=position, name=crumb.name, item=absolute_url(crumb.path))
            for position, crumb in enumerate(crumbs, start=1)
        )
    )


# `project` is duck-typed until the Project model exists.
def project_node(project: Any, path: str) -> CreativeWork:
    url = absolute_url(path)
    return CreativeWork(
        id=f"{url}#project",
        url=url,
        name=project.title,
        description=project.summary,
        author=Ref(id=PERSON_ID),
        date_published=project.published_at,
        date_modified=project.updated_at,
    )

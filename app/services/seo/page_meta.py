from dataclasses import dataclass
from datetime import datetime

from app import paths
from app.services.seo.schema_org import PageType


@dataclass(frozen=True)
class PageMeta:
    title: str
    description: str
    schema_type: PageType = "WebPage"  # schema.org @type of the page node
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

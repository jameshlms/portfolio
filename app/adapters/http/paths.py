from enum import StrEnum, unique


@unique
class Page(StrEnum):
    HOME = "/"
    ABOUT = "/about"
    CONTACT = "/contact"
    RESUME = "/resume"
    PROJECTS = "/projects"
    BLOG = "/blog"


@unique
class RootFile(StrEnum):
    """Conventional files crawlers request from the site root."""

    SITEMAP = "/sitemap.xml"
    ROBOTS = "/robots.txt"
    LLMS = "/llms.txt"
    LLMS_FULL = "/llms-full.txt"


@unique
class Internal(StrEnum):
    """Paths that serve the app itself; never advertised to crawlers."""

    ADMIN = "/admin"
    STATIC = "/static"
    HEALTH = "/healthz"


def item_path(collection: Page, slug: str) -> str:
    """Path of one item inside a collection page, e.g. /blog/my-post."""
    return f"{collection}/{slug}"

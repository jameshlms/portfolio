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
class Reserved(StrEnum):
    ADMIN = "/admin"
    STATIC = "/static"
    SITEMAP = "/sitemap.xml"
    ROBOTS = "/robots.txt"
    LLMS = "/llms.txt"
    LLMS_FULL = "/llms-full.txt"
    HEALTH = "/healthz"


def entity_path(page: Page, slug: str) -> str:
    return f"{page}/{slug}"

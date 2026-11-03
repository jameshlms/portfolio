from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from itertools import chain

from app.services.seo import page_meta
from app.services.seo.page_meta import PublishedPage
from app.services.seo.urls import absolute_asset_url, absolute_url


@dataclass(frozen=True)
class SitemapUrl:
    """One <url> element; field names follow the sitemaps.org protocol."""

    loc: str
    lastmod: datetime | None = None
    images: tuple[str, ...] = ()  # <image:image> extension


def sitemap_urls(*collections: Iterable[PublishedPage]) -> tuple[SitemapUrl, ...]:
    pages = (
        SitemapUrl(absolute_url(page))
        for page, meta in page_meta.PAGE_META.items()
        if not meta.noindex
    )
    items = (
        SitemapUrl(
            absolute_url(item.path),
            item.last_modified,
            tuple(absolute_asset_url(img) for img in item.images),
        )
        for item in chain.from_iterable(collections)
    )

    return (*pages, *items)

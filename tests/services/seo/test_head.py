from dataclasses import replace

from app import paths
from app.config import settings
from app.services.seo.head import SocialImage, for_error_page, for_page
from app.services.seo.open_graph import OpenGraphArticle


def test_home_document_title_leads_with_site_name() -> None:
    home = for_page(paths.Page.HOME)

    assert home.document_title == f"{settings.site_name} · {home.title}"


def test_other_document_titles_end_with_site_name() -> None:
    assert for_page(paths.Page.ABOUT).document_title == f"About · {settings.site_name}"


def test_error_pages_are_noindex_without_structured_data() -> None:
    page = for_error_page("Page not found", "Gone.", "/nope")

    assert page.noindex
    assert page.structured_data == ()


def test_open_graph_derives_from_page_facts() -> None:
    about = for_page(paths.Page.ABOUT)
    props = dict(about.meta_properties)

    assert props["og:type"] == "website"
    assert props["og:title"] == "About"
    assert props["og:url"] == about.canonical
    assert props["og:site_name"] == settings.site_name
    assert about.twitter_card == "summary"


def test_noindex_pages_have_no_og_url() -> None:
    props = dict(for_error_page("Page not found", "Gone.", "/nope").meta_properties)

    assert "og:url" not in props


def test_social_image_sets_og_image_and_large_card() -> None:
    page = replace(
        for_page(paths.Page.ABOUT), image=SocialImage("https://x/a.png", "Alt")
    )

    props = dict(page.meta_properties)
    assert props["og:image"] == "https://x/a.png"
    assert props["og:image:alt"] == "Alt"
    assert page.twitter_card == "summary_large_image"


def test_article_switches_og_type_and_appends_article_properties() -> None:
    page = replace(
        for_page(paths.Page.ABOUT),
        article=OpenGraphArticle(tags=("python",)),
    )

    assert dict(page.meta_properties)["og:type"] == "article"
    assert page.meta_properties[-1] == ("article:tag", "python")

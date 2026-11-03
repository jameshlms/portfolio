from app import paths
from app.config import settings
from app.services.seo.head import for_page
from app.services.seo.structured_data import PERSON_ID, WEBSITE_ID


def test_page_structured_data_is_one_linked_graph() -> None:
    graph = for_page(paths.Page.ABOUT).json_ld

    assert graph["@context"] == "https://schema.org"
    nodes = {node["@type"]: node for node in graph["@graph"]}
    assert set(nodes) == {"WebSite", "Person", "ProfilePage", "BreadcrumbList"}
    assert nodes["ProfilePage"]["isPartOf"] == {"@id": WEBSITE_ID}
    assert nodes["ProfilePage"]["mainEntity"] == {"@id": PERSON_ID}
    assert nodes["Person"]["sameAs"] == [settings.github_url, settings.linkedin_url]
    assert [i["item"] for i in nodes["BreadcrumbList"]["itemListElement"]] == [
        f"{settings.base_url}/",
        f"{settings.base_url}/about",
    ]


def test_home_has_no_breadcrumb() -> None:
    types = {node.type for node in for_page(paths.Page.HOME).structured_data}

    assert "BreadcrumbList" not in types

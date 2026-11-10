"""Blog use cases, with the in-memory repository and a fake renderer."""

from datetime import UTC, datetime, timedelta

import pytest

from app.adapters.memory_posts import InMemoryPostRepository
from app.services.blog import (
    PostSource,
    RenderedBody,
    TagCount,
    blog_index,
    get_post,
    list_published_posts,
    render_posts,
    sync_posts,
)
from app.services.errors import InvalidPost, InvalidPosts, PostNotFound, UnknownTag
from tests.blog_factories import NOW, PUBLISHED, rendered, source

pytestmark = pytest.mark.anyio


# --- Use cases -----------------------------------------------------------------


class FakeRenderer:
    """Upper-cases the body; a post whose body says CHART has one, and BROKEN fails."""

    def render(self, post: PostSource) -> RenderedBody:
        if "BROKEN" in post.markdown:
            raise InvalidPost(post.slug, {"chart x.json": "No such figure file."})
        return RenderedBody(post.markdown.upper(), has_charts="CHART" in post.markdown)


def test_render_posts_keeps_html_and_chart_flag() -> None:
    plain, charted = render_posts(
        [source("plain"), source("charted", markdown="a CHART")], FakeRenderer()
    )

    assert (plain.html, plain.has_charts) == ("BODY OF PLAIN.", False)
    assert (charted.html, charted.has_charts) == ("A CHART", True)


def test_render_posts_reports_every_failure() -> None:
    with pytest.raises(InvalidPosts) as e:
        render_posts(
            [
                source("ok"),
                source("bad-1", markdown="BROKEN"),
                source("bad-2", markdown="BROKEN"),
            ],
            FakeRenderer(),
        )

    assert [p.slug for p in e.value.posts] == ["bad-1", "bad-2"]


async def test_sync_stores_posts_and_reports_removed_ones() -> None:
    repository = InMemoryPostRepository([rendered("old"), rendered("kept")])

    removed = await sync_posts(
        [
            rendered("kept", markdown="new body"),
            rendered("new", published_at=PUBLISHED + timedelta(days=1)),
        ],
        repository,
    )

    assert removed == ("old",)
    assert (await get_post(repository, "kept", as_of=NOW)).html == "<p>new body</p>\n"
    assert [p.slug for p in await repository.published(NOW)] == ["new", "kept"]


async def test_index_reads_published_posts_and_filters_them() -> None:
    repository = InMemoryPostRepository(
        [rendered("a", tags=("python",)), rendered("b", tags=("sql",))]
    )

    index = await blog_index(repository, "python", as_of=NOW)

    assert [p.slug for p in index.posts] == ["a"]
    assert index.tags == (TagCount("python", 1), TagCount("sql", 1))


async def test_unknown_tag_is_an_error() -> None:
    repository = InMemoryPostRepository([rendered("a", tags=("python",))])

    with pytest.raises(UnknownTag):
        await blog_index(repository, "rust", as_of=NOW)


async def test_tag_used_only_by_drafts_is_unknown() -> None:
    repository = InMemoryPostRepository(
        [rendered("a", tags=("rust",), published_at=None)]
    )

    with pytest.raises(UnknownTag):
        await blog_index(repository, "rust", as_of=NOW)


async def test_missing_post_is_an_error() -> None:
    with pytest.raises(PostNotFound):
        await get_post(InMemoryPostRepository(), "nope", as_of=NOW)


async def test_last_modified_is_the_revision_if_any() -> None:
    revised = datetime(2026, 11, 1, tzinfo=UTC)
    repository = InMemoryPostRepository(
        [rendered("a"), rendered("b", revised_at=revised)]
    )

    posts = {p.slug: p for p in await repository.published(NOW)}

    assert posts["a"].last_modified == PUBLISHED
    assert posts["b"].last_modified == revised


async def test_published_posts_are_judged_at_as_of() -> None:
    launch = NOW + timedelta(days=1)
    repository = InMemoryPostRepository(
        [rendered("live"), rendered("next", published_at=launch)]
    )

    before = await list_published_posts(repository, as_of=NOW)
    after = await list_published_posts(repository, as_of=launch)

    assert [p.slug for p in before] == ["live"]
    assert [p.slug for p in after] == ["next", "live"]
    with pytest.raises(PostNotFound):
        await get_post(repository, "next", as_of=NOW)
    assert (await get_post(repository, "next", as_of=launch)).slug == "next"


async def test_as_of_defaults_to_now() -> None:
    repository = InMemoryPostRepository(
        [
            rendered("past"),
            rendered("2099", published_at=datetime(2099, 1, 1, tzinfo=UTC)),
        ]
    )

    assert [p.slug for p in await list_published_posts(repository)] == ["past"]

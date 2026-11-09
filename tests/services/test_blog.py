"""Blog use cases, with the in-memory repository and a fake renderer."""

from datetime import UTC, datetime, timedelta

import pytest

from app.adapters.memory_posts import InMemoryPostRepository
from app.domain.blog import PostSource, RenderedBody, TagCount
from app.domain.errors import InvalidPost, InvalidPosts, PostNotFound, UnknownTag
from app.services.blog import blog_index, get_post, render_posts, sync_posts
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
    assert (await get_post(repository, "kept", NOW)).html == "<p>new body</p>\n"
    assert [p.slug for p in await repository.published(NOW)] == ["new", "kept"]


async def test_index_reads_published_posts_and_filters_them() -> None:
    repository = InMemoryPostRepository(
        [rendered("a", tags=("python",)), rendered("b", tags=("sql",))]
    )

    index = await blog_index(repository, NOW, "python")

    assert [p.slug for p in index.posts] == ["a"]
    assert index.tags == (TagCount("python", 1), TagCount("sql", 1))


async def test_unknown_tag_is_an_error() -> None:
    repository = InMemoryPostRepository([rendered("a", tags=("python",))])

    with pytest.raises(UnknownTag):
        await blog_index(repository, NOW, "rust")


async def test_tag_used_only_by_drafts_is_unknown() -> None:
    repository = InMemoryPostRepository(
        [rendered("a", tags=("rust",), published_at=None)]
    )

    with pytest.raises(UnknownTag):
        await blog_index(repository, NOW, "rust")


async def test_missing_post_is_an_error() -> None:
    with pytest.raises(PostNotFound):
        await get_post(InMemoryPostRepository(), "nope", NOW)


async def test_last_modified_is_the_revision_if_any() -> None:
    revised = datetime(2026, 11, 1, tzinfo=UTC)
    repository = InMemoryPostRepository(
        [rendered("a"), rendered("b", revised_at=revised)]
    )

    posts = {p.slug: p for p in await repository.published(NOW)}

    assert posts["a"].last_modified == PUBLISHED
    assert posts["b"].last_modified == revised

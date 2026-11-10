"""Blog rules: front matter parsing and the index. Pure, no fakes needed."""

from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from app.domain.blog import (
    SUMMARY_MAX,
    PostSummary,
    TagCount,
    build_index,
    parse_post,
)
from app.domain.errors import InvalidPost, UnknownTag

_META = {
    "title": "A post",
    "summary": "What it's about.",
    "published": date(2026, 11, 7),
}


def _errors(
    slug: str = "a-post", body: str = "Body.", **meta: object
) -> dict[str, str]:
    with pytest.raises(InvalidPost) as e:
        parse_post(slug, {**_META, **meta}, body)
    return dict(e.value.errors)


# --- parse_post ----------------------------------------------------------------


def test_valid_front_matter_parses_with_dates_in_utc() -> None:
    post = parse_post(
        "a-post",
        {**_META, "tags": ["Python", "data-eng", "python"], "updated": "2026-11-08"},
        "Body.",
    )

    assert post.title == "A post"
    assert post.tags == ("python", "data-eng")  # normalized and deduplicated
    assert post.published_at == datetime(2026, 11, 7, tzinfo=UTC)
    assert post.revised_at == datetime(2026, 11, 8, tzinfo=UTC)


def test_datetimes_keep_their_time_and_convert_to_utc() -> None:
    aware = datetime(2026, 11, 7, 9, 30, tzinfo=timezone(timedelta(hours=-5)))
    naive = datetime(2026, 11, 7, 9, 30)  # noqa: DTZ001 -- YAML yields naive datetimes

    assert parse_post("a", {**_META, "published": aware}, "x").published_at == datetime(
        2026, 11, 7, 14, 30, tzinfo=UTC
    )
    assert parse_post("a", {**_META, "published": naive}, "x").published_at == datetime(
        2026, 11, 7, 9, 30, tzinfo=UTC
    )


def test_no_published_date_is_a_draft() -> None:
    meta = {k: v for k, v in _META.items() if k != "published"}

    assert parse_post("a-post", meta, "Body.").published_at is None


def test_whitespace_in_title_and_summary_is_collapsed() -> None:
    post = parse_post("a", {**_META, "title": "  Two\n  words "}, "x")

    assert post.title == "Two words"


@pytest.mark.parametrize("slug", ["Upper", "two--hyphens", "-lead", "under_score", ""])
def test_slug_must_be_url_safe(slug: str) -> None:
    assert "slug" in _errors(slug)


def test_every_problem_is_reported_at_once() -> None:
    errors = _errors(
        body="  ",
        title="",
        summary="x" * (SUMMARY_MAX + 1),
        tags="python",
        published="next tuesday",
        auhtor="typo",
    )

    assert set(errors) == {"title", "summary", "tags", "published", "auhtor", "body"}


def test_non_string_front_matter_keys_are_reported_not_crashed_on() -> None:
    # YAML reads `2026: x` with an int key; mixed with str keys, sorting would fail.
    with pytest.raises(InvalidPost) as e:
        parse_post("a-post", {**_META, 2026: "x", "auhtor": "y"}, "Body.")

    assert {"2026", "auhtor"} <= set(e.value.errors)


def test_tags_must_be_hyphenated_words() -> None:
    assert "data engineering" in _errors(tags=["data engineering"])["tags"]


def test_updated_cannot_precede_published() -> None:
    assert "updated" in _errors(updated=date(2026, 1, 1))


def test_draft_cannot_have_updated_date() -> None:
    with pytest.raises(InvalidPost) as e:
        parse_post(
            "a", {"title": "t", "summary": "s", "updated": date(2026, 1, 1)}, "x"
        )

    assert "updated" in e.value.errors


def test_figures_are_kept_read_only() -> None:
    post = parse_post("a", _META, "x", {"f.json": "{}"})

    assert dict(post.figures) == {"f.json": "{}"}
    with pytest.raises(TypeError):
        post.figures["g.json"] = "{}"  # type: ignore[index]


# --- build_index ---------------------------------------------------------------


def _summary(slug: str, *tags: str) -> PostSummary:
    published = datetime(2026, 10, 1, tzinfo=UTC)
    return PostSummary(slug, slug, "", tags, published, None)


_POSTS = (
    _summary("a", "sql", "python"),
    _summary("b", "python"),
    _summary("c", "airflow"),
)


def test_index_counts_tags_most_used_first_then_by_name() -> None:
    index = build_index(_POSTS)

    assert index.posts == _POSTS
    assert index.tags == (
        TagCount("python", 2),
        TagCount("airflow", 1),
        TagCount("sql", 1),
    )
    assert index.tag is None


def test_index_filters_by_tag_case_insensitively_but_offers_every_tag() -> None:
    index = build_index(_POSTS, " Python ")

    assert [p.slug for p in index.posts] == ["a", "b"]
    assert index.tag == "python"
    assert len(index.tags) == 3


def test_index_rejects_a_tag_no_post_carries() -> None:
    with pytest.raises(UnknownTag):
        build_index(_POSTS, "rust")

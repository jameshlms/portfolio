import json
from dataclasses import replace

import plotly.graph_objects as go
import pytest

from app.adapters.markdown import MarkdownItRenderer
from app.domain.blog import RenderedBody
from app.domain.errors import InvalidPost
from tests.blog_factories import source

_figure_json = go.Figure(go.Bar(x=["before", "after"], y=[4.2, 0.09])).to_json()
assert _figure_json is not None  # typed Optional: None only when writing to a file
_FIGURE: str = _figure_json
_CHART_POST = """Intro.

```plotly
times.json
Query time <before> and after.
```
"""


def _render(markdown: str, **figures: str) -> RenderedBody:
    post = replace(
        source(markdown=markdown),
        figures={f"{name}.json": fig for name, fig in figures.items()},
    )
    return MarkdownItRenderer().render(post)


def test_renders_commonmark_tables_and_strikethrough() -> None:
    body = _render("## Hi\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n~~old~~")

    assert "<h2>Hi</h2>" in body.html
    assert "<table>" in body.html
    assert "<s>old</s>" in body.html
    assert body.has_charts is False


def test_raw_html_is_escaped_not_rendered() -> None:
    html = _render('<script>alert(1)</script>\n\nText <img src=x onerror="y">').html

    assert "<script>" not in html
    assert "<img" not in html
    assert "&lt;script&gt;" in html


def test_javascript_links_are_not_linked() -> None:
    assert "href" not in _render("[click](javascript:alert(1))").html


def test_other_fences_stay_code_blocks() -> None:
    html = _render("```python\nprint('hi')\n```").html

    assert '<pre><code class="language-python">' in html


def test_plotly_fence_embeds_the_figure_with_an_escaped_caption() -> None:
    body = _render(_CHART_POST, times=_FIGURE)

    assert body.has_charts is True
    assert '<figure class="post-chart"><div class="post-chart__plot">' in body.html
    assert 'id="chart-1"' in body.html
    assert "Plotly.newPlot" in body.html
    assert "<figcaption>Query time &lt;before&gt; and after.</figcaption>" in body.html
    assert "<script src=" not in body.html  # plotly.js itself comes from the page


def test_chart_html_is_the_same_on_every_sync() -> None:
    # Random ids would make every deploy look like an edit (and bump updated_at).
    twice = _CHART_POST + "\n" + _CHART_POST

    first = _render(twice, times=_FIGURE).html

    assert first == _render(twice, times=_FIGURE).html
    assert 'id="chart-1"' in first
    assert 'id="chart-2"' in first


def test_chart_without_caption_has_no_figcaption() -> None:
    assert (
        "<figcaption>" not in _render("```plotly\ntimes.json\n```", times=_FIGURE).html
    )


@pytest.mark.parametrize(
    ("markdown", "figures", "error_key"),
    [
        ("```plotly\nmissing.json\n```", {}, "chart missing.json"),
        ("```plotly\n```", {}, "chart (unnamed)"),
        ("```plotly\nbad.json\n```", {"bad": "{not json"}, "chart bad.json"),
        (
            "```plotly\nbad.json\n```",
            {"bad": json.dumps({"data": [{"type": "nope"}]})},
            "chart bad.json",
        ),
    ],
)
def test_bad_chart_makes_the_post_invalid(
    markdown: str, figures: dict[str, str], error_key: str
) -> None:
    with pytest.raises(InvalidPost) as e:
        _render(markdown, **figures)

    assert error_key in e.value.errors

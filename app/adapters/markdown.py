"""MarkdownRenderer backed by markdown-it-py: CommonMark plus GFM tables and
strikethrough, and Plotly charts embedded with a `plotly` fence:

    ```plotly
    query-times.json
    Optional caption, which can run over several lines.
    ```

The first line names a figure file beside the post (content/blog/<slug>/),
written with `fig.write_json(...)`; the rest is the caption.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from html import escape
from typing import Any

import plotly.io as pio
from markdown_it import MarkdownIt
from markdown_it.renderer import RendererHTML
from markdown_it.token import Token
from markdown_it.utils import OptionsDict

from app.adapters.charts import render_chart
from app.domain.blog import PostSource, RenderedBody
from app.domain.errors import InvalidPost

_CHART_FENCE = "plotly"


@dataclass
class _Charts:
    """What the fence rule needs and reports for one render (markdown-it's `env`)."""

    figures: Mapping[str, str]
    count: int = 0
    errors: dict[str, str] = field(default_factory=dict)


class MarkdownItRenderer:
    def __init__(self) -> None:
        # Raw HTML is off: the output is only what Markdown itself produces (plus
        # charts built from figure data), so it's safe to mark |safe in templates.
        # markdown-it also refuses javascript: links.
        self._md = MarkdownIt("commonmark", {"html": False}).enable(
            ["table", "strikethrough"]
        )

        def fence(
            renderer: RendererHTML,
            tokens: Sequence[Token],
            idx: int,
            options: OptionsDict,
            env: dict[str, Any],
        ) -> str:
            token = tokens[idx]
            if token.info.strip() != _CHART_FENCE:
                # The built-in rule: add_render_rule replaces the entry, not the method.
                return RendererHTML.fence(renderer, tokens, idx, options, env)
            return _chart(token.content, env["charts"])

        self._md.add_render_rule("fence", fence)

    def render(self, post: PostSource) -> RenderedBody:
        charts = _Charts(post.figures)
        html = self._md.render(post.markdown, {"charts": charts})
        if charts.errors:
            raise InvalidPost(post.slug, charts.errors)
        return RenderedBody(html, has_charts=charts.count > 0)


def _chart(content: str, charts: _Charts) -> str:
    name, *caption_lines = [line.strip() for line in content.strip().splitlines()] or [
        ""
    ]
    figure_json = charts.figures.get(name)
    if figure_json is None:
        charts.errors[f"chart {name or '(unnamed)'}"] = (
            "No such figure file in the post's folder."
            if name
            else "Name a figure file on the fence's first line."
        )
        return ""
    try:
        figure = pio.from_json(figure_json)
    except ValueError as e:
        charts.errors[f"chart {name}"] = f"Not a valid Plotly figure: {e}"
        return ""

    charts.count += 1
    # A fixed id keeps the HTML identical between syncs (plotly's default is random).
    plot = render_chart(figure, div_id=f"chart-{charts.count}")
    caption = " ".join(line for line in caption_lines if line)
    figcaption = f"<figcaption>{escape(caption)}</figcaption>" if caption else ""
    return (
        f'<figure class="post-chart"><div class="post-chart__plot">{plot}</div>'
        f"{figcaption}</figure>\n"
    )

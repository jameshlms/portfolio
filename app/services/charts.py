from markupsafe import Markup
from plotly.graph_objects import Figure
from plotly.io import to_html

_BASE_CONFIG = {"responsive": True, "displaylogo": False}


def render_chart(
    fig: Figure,
    *,
    div_id: str | None = None,
    config: dict | None = None,
) -> Markup:
    """Chart markup without plotly.js; the page must include components/_plotly.html."""
    html = to_html(
        fig,
        full_html=False,
        include_plotlyjs=False,
        default_height="100%",
        default_width="100%",
        div_id=div_id,
        config={**_BASE_CONFIG, **(config or {})},
    )
    return Markup(html)

"""Template layout rules, checked from the source.

templates/
  base.html     the layout every page extends
  pages/        whole pages; routes render them
  errors/       the error page; the exception handlers render it
  seo/          crawler files (sitemap.xml, robots.txt, llms.txt)
  components/   partials, only ever {% include %}d by other templates
  fragments/    partials returned on their own for htmx to swap in, by a route
                or (fragments/_error.html) the exception handlers

A fragment's outermost element (besides a <title> for the tab) carries the id
its hx-target names, so an outerHTML swap leaves that target in the page for the
next request. Every branch of a fragment must keep it.
"""

import ast
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import ClassVar

import pytest
from jinja2 import meta

from app import APP_DIR
from app.templates import make_templates

TEMPLATES = APP_DIR / "templates"
_FOLDERS = {"pages", "errors", "seo", "components", "fragments"}
_RENDERABLE = ("pages/", "errors/", "seo/", "fragments/")

_env = make_templates().env


def _templates() -> list[str]:
    return sorted(
        str(p.relative_to(TEMPLATES)) for p in TEMPLATES.rglob("*") if p.is_file()
    )


def _template_literals(path: Path) -> set[str]:
    """String constants in a Python file that name a template."""
    return {
        node.value
        for node in ast.walk(ast.parse(path.read_text()))
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and re.fullmatch(r"[\w/.-]+\.(html|j2)", node.value)
    }


_PYTHON = sorted(APP_DIR.rglob("*.py"))
_RENDERED = {
    name: path for path in _PYTHON for name in _template_literals(path)
}  # template -> a file that renders it


def test_every_template_lives_in_a_known_folder() -> None:
    stray = [
        t for t in _templates() if t != "base.html" and t.split("/")[0] not in _FOLDERS
    ]

    assert stray == []


@pytest.mark.parametrize("name", sorted(_RENDERED), ids=str)
def test_python_renders_only_pages_errors_seo_and_fragments(name: str) -> None:
    assert name.startswith(_RENDERABLE), (
        f"{_RENDERED[name].name} renders {name}; components are include-only. "
        "Move it to fragments/ if a route returns it on its own."
    )


@pytest.mark.parametrize("name", sorted(_RENDERED), ids=str)
def test_every_rendered_template_exists(name: str) -> None:
    assert (TEMPLATES / name).is_file()


_FRAGMENTS = [t for t in _templates() if t.startswith("fragments/")]


@pytest.mark.parametrize("name", _FRAGMENTS, ids=str)
def test_every_fragment_is_returned_on_its_own(name: str) -> None:
    assert name in _RENDERED, (
        f"Nothing returns {name} on its own: move it to components/."
    )


class _TopLevel(HTMLParser):
    """The outermost elements of an HTML snippet, as (tag, id)."""

    _VOID: ClassVar[frozenset[str]] = frozenset(
        {
            "area",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "source",
            "wbr",
        }
    )

    def __init__(self) -> None:
        super().__init__()
        self.depth = 0
        self.elements: list[tuple[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.depth == 0:
            self.elements.append((tag, dict(attrs).get("id")))
        if tag not in self._VOID:
            self.depth += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.depth == 0:
            self.elements.append((tag, dict(attrs).get("id")))

    def handle_endtag(self, tag: str) -> None:
        if tag not in self._VOID:
            self.depth -= 1


def _outermost(source: str) -> list[tuple[str, str | None]]:
    # Drop Jinja so every branch's markup is visible; keep expressions as text.
    html = re.sub(r"\{#.*?#\}|\{%.*?%\}", "", source, flags=re.DOTALL)
    html = re.sub(r"\{\{.*?\}\}", "x", html, flags=re.DOTALL)
    parser = _TopLevel()
    parser.feed(html)
    return [element for element in parser.elements if element[0] != "title"]


@pytest.mark.parametrize("name", _FRAGMENTS, ids=str)
def test_fragments_keep_their_swap_target_in_every_branch(name: str) -> None:
    elements = _outermost((TEMPLATES / name).read_text())
    ids = {element_id for _, element_id in elements}

    assert elements, f"{name} has no markup"
    assert None not in ids, f"An outermost element of {name} has no id: {elements}"
    assert len(ids) == 1, f"{name}'s outermost elements disagree on the id: {ids}"


@pytest.mark.parametrize("name", _templates(), ids=str)
def test_includes_extends_and_imports_resolve(name: str) -> None:
    source = (TEMPLATES / name).read_text()
    referenced = meta.find_referenced_templates(_env.parse(source))
    missing = [r for r in referenced if r is not None and not (TEMPLATES / r).is_file()]

    assert missing == []

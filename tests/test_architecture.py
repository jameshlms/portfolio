"""The feature modules stay free of infrastructure: services/blog.py, contact.py and
errors.py hold the rules, so they import only the standard library, each other and
Pydantic (which validates their untrusted input: front matter, the contact form).
Anything that touches a database, HTTP or a web framework lives in adapters/,
routes/ or deps/.
"""

import ast
import sys
from pathlib import Path

import pytest

SERVICES = Path(__file__).resolve().parent.parent / "app" / "services"
_FEATURES = ("blog.py", "contact.py", "errors.py")
_SIBLINGS = {f"app.services.{name.removesuffix('.py')}" for name in _FEATURES}
_VALIDATION = {"pydantic", "pydantic_core"}


def _imports(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            modules |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


@pytest.mark.parametrize("name", _FEATURES)
def test_feature_modules_import_only_the_stdlib_pydantic_and_each_other(
    name: str,
) -> None:
    bad = {
        m
        for m in _imports(SERVICES / name)
        if m.split(".")[0] not in sys.stdlib_module_names
        and m != "__future__"
        and m not in _SIBLINGS
        and m.split(".")[0] not in _VALIDATION
    }

    assert bad == set()

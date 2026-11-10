"""The feature modules stay pure: services/blog.py, contact.py and errors.py hold
the rules, so they import only the standard library and each other. Anything that
touches a database, HTTP or a framework lives in adapters/, routes/ or deps/.
"""

import ast
import sys
from pathlib import Path

import pytest

SERVICES = Path(__file__).resolve().parent.parent / "app" / "services"
_FEATURES = ("blog.py", "contact.py", "errors.py")
_SIBLINGS = {f"app.services.{name.removesuffix('.py')}" for name in _FEATURES}


def _imports(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            modules |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


@pytest.mark.parametrize("name", _FEATURES)
def test_feature_modules_import_only_the_stdlib_and_each_other(name: str) -> None:
    bad = {
        m
        for m in _imports(SERVICES / name)
        if m.split(".")[0] not in sys.stdlib_module_names
        and m != "__future__"
        and m not in _SIBLINGS
    }

    assert bad == set()

"""The dependency rule, checked from the source: adapters -> ports -> domain.

The domain imports only the standard library and itself. Ports import only the
standard library and the domain. Nothing in either may reach infrastructure.
"""

import ast
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parent.parent / "app"


def _imports(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            modules |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


def _files(layer: str) -> list[Path]:
    return sorted((APP / layer).rglob("*.py"))


def _allowed(module: str, packages: tuple[str, ...]) -> bool:
    top = module.split(".")[0]
    return (
        top in sys.stdlib_module_names
        or module == "__future__"
        or any(module == p or module.startswith(f"{p}.") for p in packages)
    )


@pytest.mark.parametrize("path", _files("domain"), ids=lambda p: p.name)
def test_domain_imports_only_itself_and_the_stdlib(path: Path) -> None:
    bad = {m for m in _imports(path) if not _allowed(m, ("app.domain",))}

    assert bad == set()


@pytest.mark.parametrize(
    "path", _files("ports"), ids=lambda p: str(p.relative_to(APP / "ports"))
)
def test_ports_import_only_the_domain_and_the_stdlib(path: Path) -> None:
    bad = {m for m in _imports(path) if not _allowed(m, ("app.domain", "app.ports"))}

    assert bad == set()


def test_the_layers_have_files_to_check() -> None:
    assert _files("domain") and _files("ports")

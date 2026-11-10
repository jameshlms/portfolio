"""The dependency rule, checked from the source: adapters -> ports -> domain.

- The domain imports only the standard library and itself.
- Ports import only the standard library and the domain.
- Use cases (services) import only the domain and ports.
- The Container holds ports, so it imports only ports and the domain.
- Adapters don't import each other; each is wired to the others through ports,
  by app.bootstrap. Only the entry points (app.main, app.__main__) import that.
- HTTP routes reach the hexagon through use cases: they import services, never
  port types (the ports they pass along arrive typed, from app.adapters.http.deps).
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


@pytest.mark.parametrize("path", _files("services"), ids=lambda p: p.name)
def test_use_cases_import_only_the_domain_and_ports(path: Path) -> None:
    bad = {m for m in _imports(path) if not _allowed(m, ("app.domain", "app.ports"))}

    assert bad == set()


def test_the_container_holds_only_ports() -> None:
    imports = _imports(APP / "container.py")

    assert {m for m in imports if not _allowed(m, ("app.domain", "app.ports"))} == set()


# Not an adapter (it fills no port): Plotly figure -> HTML, shared by renderers.
_SHARED_HELPERS = {"charts"}


def _adapter(module_or_path: str) -> str:
    """The adapter a module belongs to: its package or module under app/adapters."""
    return module_or_path.removeprefix("app.adapters.").split(".")[0]


_ADAPTER_FILES = sorted((APP / "adapters").rglob("*.py"))


@pytest.mark.parametrize(
    "path", _ADAPTER_FILES, ids=lambda p: str(p.relative_to(APP / "adapters"))
)
def test_adapters_do_not_import_other_adapters_or_the_bootstrap(path: Path) -> None:
    own = path.relative_to(APP / "adapters").with_suffix("").parts[0]
    others = {
        m
        for m in _imports(path)
        if m.startswith("app.adapters.") and _adapter(m) not in {own, *_SHARED_HELPERS}
    }
    composition = {m for m in _imports(path) if m in {"app.bootstrap", "app.main"}}

    assert others == set()
    assert composition == set()


_ROUTE_FILES = sorted((APP / "adapters" / "http" / "routes").glob("*.py"))


@pytest.mark.parametrize("path", _ROUTE_FILES, ids=lambda p: p.name)
def test_routes_use_use_cases_not_ports(path: Path) -> None:
    ports = {
        m for m in _imports(path) if m == "app.ports" or m.startswith("app.ports.")
    }

    assert ports == set()


def test_the_layers_have_files_to_check() -> None:
    assert _files("domain") and _files("ports") and _ADAPTER_FILES and _ROUTE_FILES

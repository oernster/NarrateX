"""Dependency direction between the layers, read from every import a module makes.

What counts as an import, so the rule cannot be stepped round by spelling:

- `import voice_reader.x.y` and `from voice_reader.x import y`;
- package-level imports, `from voice_reader import infrastructure`, read as
  `voice_reader.infrastructure`;
- relative imports, `from ..infrastructure.books import parser`, resolved
  against the importing module's own package;
- `importlib.import_module(...)` and `__import__(...)` called with a string
  constant that names the package. A dynamic import of a computed name cannot
  be read statically and is not claimed.

The companion tests at the foot plant each spelling in a scratch tree and
prove the scan reports it.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

_PACKAGE = "voice_reader"

_LAYERS = ("domain", "application", "infrastructure", "ui", "shared")

# Which layer roots each layer may import. UI may import anything but
# Infrastructure; Domain and Shared import nothing outside themselves.
_ALLOWED: dict[str, frozenset[str]] = {
    "shared": frozenset({"shared"}),
    "domain": frozenset({"domain"}),
    "application": frozenset({"application", "domain", "shared"}),
    "infrastructure": frozenset({"infrastructure", "domain", "shared"}),
    "ui": frozenset({"ui", "application", "domain", "shared"}),
}

_DYNAMIC_IMPORTERS = frozenset({"import_module", "__import__"})


@dataclass(frozen=True, slots=True)
class ImportViolation:
    importer: str
    imported: str
    rule: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _module_parts(rel: str) -> list[str]:
    parts = rel[: -len(".py")].split("/")
    return parts[:-1] if parts[-1] == "__init__" else parts


def _package_parts(rel: str) -> list[str]:
    parts = rel[: -len(".py")].split("/")
    return parts[:-1]


def _resolved_from(node: ast.ImportFrom, rel: str) -> str:
    if node.level == 0:
        return node.module or ""
    package = _package_parts(rel)
    base = package[: len(package) - (node.level - 1)]
    return ".".join(base + ([node.module] if node.module else []))


def _dynamic_target(node: ast.Call) -> str | None:
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
    if name not in _DYNAMIC_IMPORTERS or not node.args:
        return None
    first = node.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return None


def _imports(tree: ast.AST, rel: str) -> set[str]:
    """Every module this tree imports, as a dotted absolute name."""

    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = _resolved_from(node, rel)
            found.add(module)
            # `from voice_reader import infrastructure` names a layer by its
            # alias, so each imported name is read as a submodule too.
            found.update(f"{module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Call):
            target = _dynamic_target(node)
            if target is not None:
                found.add(target)
    return found


def _layer_of_module(dotted: str) -> str | None:
    parts = dotted.split(".")
    if len(parts) >= 2 and parts[0] == _PACKAGE and parts[1] in _LAYERS:
        return parts[1]
    return None


def _layer_of_file(rel: str) -> str | None:
    parts = rel.split("/")
    if len(parts) >= 3 and parts[0] == _PACKAGE and parts[1] in _LAYERS:
        return parts[1]
    return None


def _violations(root: Path) -> list[ImportViolation]:
    violations: list[ImportViolation] = []
    for path in sorted((root / _PACKAGE).rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        layer = _layer_of_file(rel)
        if layer is None:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        for imported in sorted(_imports(tree, rel)):
            target = _layer_of_module(imported)
            if target is None or target in _ALLOWED[layer]:
                continue
            violations.append(
                ImportViolation(
                    importer=rel,
                    imported=imported,
                    rule=f"{layer} may import only {sorted(_ALLOWED[layer])}",
                )
            )
    return violations


def test_layering_rules_for_voice_reader_are_respected() -> None:
    violations = _violations(_repo_root())

    assert not violations, "Layering rules violated:\n" + "\n".join(
        f"- {v.importer} imports {v.imported} ({v.rule})" for v in violations
    )


def test_the_scan_reads_every_layer_it_judges() -> None:
    """A scan that found no files would pass every rule it states."""

    root = _repo_root()
    seen = {
        _layer_of_file(p.relative_to(root).as_posix())
        for p in (root / _PACKAGE).rglob("*.py")
    }

    assert set(_LAYERS) <= seen


# Companion tests: each spelling, planted, must be reported. ----------------


def _plant(root: Path, rel: str, source: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def _reported(tmp_path: Path, rel: str, source: str) -> list[str]:
    _plant(tmp_path, rel, source)
    return [v.imported for v in _violations(tmp_path)]


def test_a_package_level_import_is_reported(tmp_path: Path) -> None:
    source = "from voice_reader import infrastructure\n"

    assert _reported(tmp_path, "voice_reader/ui/x.py", source) == [
        "voice_reader.infrastructure"
    ]


def test_a_package_level_import_from_the_domain_is_reported(tmp_path: Path) -> None:
    source = "from voice_reader import infrastructure\n"

    assert _reported(tmp_path, "voice_reader/domain/x.py", source) == [
        "voice_reader.infrastructure"
    ]


def test_a_relative_import_is_resolved_and_reported(tmp_path: Path) -> None:
    source = "from ..infrastructure.books import parser\n"

    assert _reported(tmp_path, "voice_reader/ui/x.py", source) == [
        "voice_reader.infrastructure.books",
        "voice_reader.infrastructure.books.parser",
    ]


def test_a_dynamic_import_naming_the_package_is_reported(tmp_path: Path) -> None:
    source = (
        "import importlib\n"
        'importlib.import_module("voice_reader.infrastructure.books.parser")\n'
        '__import__("voice_reader.infrastructure")\n'
    )

    assert _reported(tmp_path, "voice_reader/ui/x.py", source) == [
        "voice_reader.infrastructure",
        "voice_reader.infrastructure.books.parser",
    ]


def test_permitted_imports_are_not_reported(tmp_path: Path) -> None:
    source = (
        "from . import sibling\n"
        "from .. import application\n"
        "from voice_reader.application.services import bookmark_service\n"
        "from voice_reader import version\n"
        "import importlib\n"
        "importlib.import_module(name)\n"
    )

    assert _reported(tmp_path, "voice_reader/ui/x.py", source) == []

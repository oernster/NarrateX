from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


_KNOWN_LAYER_ROOTS = {
    "voice_reader.domain",
    "voice_reader.application",
    "voice_reader.infrastructure",
    "voice_reader.ui",
    "voice_reader.shared",
}


@dataclass(frozen=True, slots=True)
class ImportViolation:
    importer: str
    imported: str
    rule: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _iter_in_scope_source_files(root: Path) -> list[Path]:
    excluded = {
        ".git",
        "__pycache__",
        "venv",
        ".venv",
        "build",
        "dist",
        "dist-pyinstaller",
    }

    out: list[Path] = []
    for p in root.rglob("*.py"):
        if excluded & {part.lower() for part in p.parts}:
            continue
        rel = p.relative_to(root).as_posix()
        if rel.startswith(("voice_reader/", "installer/", "tests/")) or rel in {
            "app.py",
            "buildexe.py",
            "buildinstaller.py",
            "generate_scripts.py",
        }:
            out.append(p)
    return out


def _parse_imports(path: Path) -> set[str]:
    """Return imported module roots as fully-qualified strings.

    We only care about our own package boundaries here, so we return the top-level
    module name(s) (e.g. "voice_reader.ui", "voice_reader.infrastructure").
    """

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return set()

    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        # If a file is syntactically broken, the normal test suite will fail anyway.
        return set()

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if isinstance(alias.name, str) and alias.name:
                    imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if isinstance(node.module, str) and node.module:
                imported.add(node.module)
    return imported


def _voice_reader_root(imported: str) -> str | None:
    """Return a normalized `voice_reader.<layer>` root if applicable.

    We intentionally ignore non-layer modules like `voice_reader.version`.
    """

    if not imported.startswith("voice_reader."):
        return None

    parts = imported.split(".")
    if len(parts) < 2:
        return None

    root = ".".join(parts[:2])
    if root in _KNOWN_LAYER_ROOTS:
        return root
    return None


def _layer_for(path: str) -> str | None:
    if path.startswith("voice_reader/domain/"):
        return "domain"
    if path.startswith("voice_reader/application/"):
        return "application"
    if path.startswith("voice_reader/infrastructure/"):
        return "infrastructure"
    if path.startswith("voice_reader/ui/"):
        return "ui"
    if path.startswith("voice_reader/shared/"):
        return "shared"
    return None


def _is_voice_reader_module(imported: str) -> bool:
    return imported == "voice_reader" or imported.startswith("voice_reader.")


def test_layering_rules_for_voice_reader_are_respected() -> None:
    """Hard-enforced layering rules.

    Rules (as specified in the refactor brief, normalized to intra-package reality):
    - Shared must not import *upwards* (domain/application/ui/infrastructure).
    - Domain must not import *upwards* (application/ui/infrastructure/shared).
      Domain-to-domain imports are allowed.
    - Application may import: domain + shared (+ application itself).
      Application must not import: ui, infrastructure.
    - Infrastructure may import: domain + shared (+ infrastructure itself).
      Infrastructure must not import: ui, application.
    - UI must not import infrastructure.
    """

    root = _repo_root()
    violations: list[ImportViolation] = []

    for p in _iter_in_scope_source_files(root):
        rel = p.relative_to(root).as_posix()
        layer = _layer_for(rel)
        if layer is None:
            continue

        imported = _parse_imports(p)
        voice_reader_imports = sorted(
            {m for m in imported if _is_voice_reader_module(m)}
        )
        roots: set[str] = set()
        for m in voice_reader_imports:
            r = _voice_reader_root(m)
            if r is not None:
                roots.add(r)
        voice_reader_roots = sorted(roots)

        if layer == "shared":
            # Shared is a bottom layer: it should not import other voice_reader layers.
            for r in voice_reader_roots:
                if r == "voice_reader.shared":
                    continue
                violations.append(
                    ImportViolation(
                        importer=rel,
                        imported=r,
                        rule="Shared must not import domain/application/ui/infrastructure",
                    )
                )

        elif layer == "domain":
            # Domain is allowed to import within itself.
            for r in voice_reader_roots:
                if r == "voice_reader.domain":
                    continue
                violations.append(
                    ImportViolation(
                        importer=rel,
                        imported=r,
                        rule="Domain must not import outside voice_reader.domain",
                    )
                )

        elif layer == "application":
            # Application may import itself, domain, and shared.
            allowed_roots = {
                "voice_reader.application",
                "voice_reader.domain",
                "voice_reader.shared",
            }
            for r in voice_reader_roots:
                if r in allowed_roots:
                    continue
                violations.append(
                    ImportViolation(
                        importer=rel,
                        imported=r,
                        rule="Application must not import UI or Infrastructure",
                    )
                )

        elif layer == "infrastructure":
            # Infrastructure may import itself, domain, and shared.
            allowed_roots = {
                "voice_reader.infrastructure",
                "voice_reader.domain",
                "voice_reader.shared",
            }
            for r in voice_reader_roots:
                if r in allowed_roots:
                    continue
                violations.append(
                    ImportViolation(
                        importer=rel,
                        imported=r,
                        rule="Infrastructure must not import UI or Application",
                    )
                )

        elif layer == "ui":
            # UI may import itself, application, domain, and (sparingly) shared.
            # But UI must never import infrastructure.
            for r in voice_reader_roots:
                if r == "voice_reader.infrastructure":
                    violations.append(
                        ImportViolation(
                            importer=rel,
                            imported=r,
                            rule="UI must not import voice_reader.infrastructure",
                        )
                    )

    if violations:
        details = "\n".join(
            f"- {v.importer} imports {v.imported} ({v.rule})" for v in violations
        )
        raise AssertionError("Layering rules violated:\n" + details)

from __future__ import annotations

import ast
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _parse_imported_modules(path: Path) -> set[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return set()

    tree = ast.parse(text, filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module)
    return imported


def _is_whitelisted_composition_root(rel: str) -> bool:
    if rel in {
        "app.py",
        "installer/app.py",
        "voice_reader/bootstrap.py",
    }:
        return True
    return False


def _voice_reader_root(imported: str) -> str | None:
    if not imported.startswith("voice_reader."):
        return None
    parts = imported.split(".")
    if len(parts) < 2:
        return None
    return ".".join(parts[:2])


def test_bootstrap_is_only_imported_by_entrypoints() -> None:
    """`voice_reader.bootstrap` is a composition-root helper, not a general dependency."""

    root = _repo_root()
    bootstrap = root / "voice_reader" / "bootstrap.py"
    assert bootstrap.exists(), "Expected voice_reader/bootstrap.py to exist"

    allowed_importers = {
        "app.py",
        "installer/app.py",
    }

    offenders: list[str] = []
    excluded = {
        ".git",
        "__pycache__",
        "venv",
        ".venv",
        "build",
        "dist",
        "dist-pyinstaller",
    }
    for p in root.rglob("*.py"):
        if excluded & {part.lower() for part in p.parts}:
            continue

        rel = p.relative_to(root).as_posix()
        if rel == "voice_reader/bootstrap.py":
            continue
        imported = _parse_imported_modules(p)
        if any(
            m == "voice_reader.bootstrap" or m.startswith("voice_reader.bootstrap")
            for m in imported
        ):
            if rel not in allowed_importers:
                offenders.append(rel)

    if offenders:
        offenders_sorted = "\n".join(f"- {p}" for p in sorted(offenders))
        raise AssertionError(
            "voice_reader.bootstrap must only be imported by whitelisted entrypoints.\n"
            + offenders_sorted
        )


def test_only_composition_roots_may_import_both_application_and_infrastructure() -> (
    None
):
    """Enforce the "composition root" wiring constraint.

    Wiring concrete infrastructure implementations into application services requires
    referencing both layers. This must only happen in whitelisted composition roots.
    """

    root = _repo_root()
    offenders: list[str] = []

    excluded = {
        ".git",
        "__pycache__",
        "venv",
        ".venv",
        "build",
        "dist",
        "dist-pyinstaller",
    }

    for p in root.rglob("*.py"):
        if excluded & {part.lower() for part in p.parts}:
            continue

        rel = p.relative_to(root).as_posix()
        # Only enforce this for production code / entrypoints.
        if rel.startswith("tests/"):
            continue

        imported = _parse_imported_modules(p)
        roots = {r for m in imported for r in [_voice_reader_root(m)] if r is not None}
        has_app = "voice_reader.application" in roots
        has_infra = "voice_reader.infrastructure" in roots

        if has_app and has_infra and not _is_whitelisted_composition_root(rel):
            offenders.append(rel)

    if offenders:
        details = "\n".join(f"- {p}" for p in sorted(offenders))
        raise AssertionError(
            "Only whitelisted composition roots may import both voice_reader.application and "
            "voice_reader.infrastructure.\n" + details
        )

"""Structural guard: narration is always built from a document model.

`NavigationChunkService.build_chunks` takes the document that decides what is
spoken and where the body begins. Its callers sit inside broad
`except Exception` handlers that keep a book load from failing outright, so a
call that omits the document does not raise: it silently yields no chapters and
a disabled pair of navigation buttons, which reads exactly like a book that has
no chapters.

An AST scan constrains that state instead of relying on someone noticing it.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

_METHOD = "build_chunks"
_REQUIRED_KEYWORD = "document"


def _repo_root() -> Path:
    # tests/structural/test_narration_contracts.py -> structural -> tests -> repo
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class CallSite:
    path: str
    line: int


def _source_files(root: Path) -> list[Path]:
    package = root / "voice_reader"
    return sorted(p for p in package.rglob("*.py") if "__pycache__" not in p.parts)


def _offending_call_sites(path: Path, *, root: Path) -> list[CallSite]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):  # pragma: no cover - unreadable file
        return []

    offenders: list[CallSite] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != _METHOD:
            continue

        keywords = {kw.arg for kw in node.keywords}
        # `**kwargs` forwarding arrives as arg=None and is not inspectable, so
        # it is trusted rather than reported.
        if None in keywords or _REQUIRED_KEYWORD in keywords:
            continue

        offenders.append(
            CallSite(path=path.relative_to(root).as_posix(), line=node.lineno)
        )
    return offenders


def test_every_build_chunks_call_supplies_a_document() -> None:
    root = _repo_root()

    offenders = [
        site
        for path in _source_files(root)
        for site in _offending_call_sites(path, root=root)
    ]

    details = "\n".join(f"- {s.path}:{s.line}" for s in offenders)
    assert not offenders, (
        f"Every call to {_METHOD}() must pass {_REQUIRED_KEYWORD}=, so narration "
        "cannot fall back to speaking an unstructured book by accident.\n"
        f"{details}"
    )

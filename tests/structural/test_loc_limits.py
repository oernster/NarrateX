from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LocOffender:
    path: str
    lines: int


def _repo_root() -> Path:
    # tests/structural/test_loc_limits.py -> tests/structural -> tests -> repo
    return Path(__file__).resolve().parents[2]


def _is_in_scope_python_file(path: Path, *, repo_root: Path) -> bool:
    if path.suffix != ".py":
        return False

    parts = {p.lower() for p in path.parts}
    excluded = {
        ".git",
        "__pycache__",
        "venv",
        ".venv",
        "build",
        "dist",
        "dist-pyinstaller",
    }
    if parts & excluded:
        return False

    # "Everything" means everything that is part of this repo's code and tests,
    # not vendored site-packages or PyInstaller output.
    try:
        rel = path.relative_to(repo_root).as_posix()
    except Exception:
        return False
    return rel.startswith(
        (
            "voice_reader/",
            "installer/",
            "tests/",
        )
    ) or path.name in {
        "app.py",
        "buildexe.py",
        "buildinstaller.py",
        "generate_scripts.py",
    }


def _count_physical_lines(path: Path) -> int:
    # Physical lines, not logical LOC.
    # Use tolerant decoding to avoid tripping on odd encodings in artefacts.
    return sum(1 for _ in path.open("r", encoding="utf-8", errors="ignore"))


def test_all_in_scope_python_files_are_at_most_400_lines() -> None:
    root = _repo_root()
    offenders: list[LocOffender] = []

    for p in root.rglob("*.py"):
        if not _is_in_scope_python_file(p, repo_root=root):
            continue
        lines = _count_physical_lines(p)
        if lines > 400:
            offenders.append(
                LocOffender(path=p.relative_to(root).as_posix(), lines=lines)
            )

    if offenders:
        offenders_sorted = sorted(
            offenders, key=lambda o: (o.lines, o.path), reverse=True
        )
        details = "\n".join(f"- {o.lines:4d}  {o.path}" for o in offenders_sorted)
        raise AssertionError(
            "File size constraint violated: every in-scope *.py must be <= 400 lines.\n"
            + details
        )

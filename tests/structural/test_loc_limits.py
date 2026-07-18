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


# Delivery scripts and their helpers, wherever they sit. Length is not a
# defect in these.
_BUILD_SCRIPTS = frozenset(
    {
        "buildexe.py",
        "buildinstaller.py",
        "builddmg.py",
        "dmg_icon.py",
        "build_utils.py",
        "build_payload.py",
        "generate_icons.py",
        "generate_scripts.py",
        "stamp_version.py",
    }
)


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
        ".flatpak-build",
        ".flatpak-builder",
        ".flatpak-repo",
        ".flatpak-wheels",
    }
    if parts & excluded:
        return False

    # "Everything" means everything that is part of this repo's code and tests,
    # not vendored site-packages or PyInstaller output.
    try:
        rel = path.relative_to(repo_root).as_posix()
    except Exception:
        return False

    # Build and packaging scripts are exempt from the cap. They are linear
    # recipes read top to bottom, where splitting a sequence of flags and steps
    # across modules costs more than it buys. The exemption is listed rather
    # than left to chance: `builddmg.py` used to escape only by not appearing
    # in the whitelist below, while its siblings were held to the cap.
    if path.name in _BUILD_SCRIPTS:
        return False

    return rel.startswith(
        (
            "voice_reader/",
            "installer/",
            "tests/",
        )
    ) or path.name in {"app.py"}


def _count_physical_lines(path: Path) -> int:
    # Physical lines, not logical LOC.
    # Use tolerant decoding to avoid tripping on odd encodings in artefacts.
    return sum(1 for _ in path.open("r", encoding="utf-8", errors="ignore"))


# REFACTORING RULE (the 5% rule): 400 is the limit and the normal target, so a
# file below it and clear of the band below needs nothing doing to it.
#
# 5% of 400 is 20, so >380 and <400 (381 to 399) is the danger band. A file
# sitting in that band is reduced to <=350, never left at 399. That covers both
# a file that grew into the band and a file refactored down from over the cap,
# which must land at <=350 rather than stopping the moment it clears 400.
#
# Skimming 1-2 lines at a time to stay just under 400 buys nothing: the next edit
# breaks it again and the same file gets refactored over and over. Extract a
# cohesive module instead. See ARCHITECTURE_CONSTRAINTS.md section 3.
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

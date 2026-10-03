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


# Delivery scripts and their helpers, by their path from the repository root.
# Length is not a defect in these. A path rather than a bare name, so a module
# that merely shares a name with one (`voice_reader/ui/generate_icons.py`) is
# measured like any other.
_BUILD_SCRIPTS = frozenset(
    {
        "buildexe.py",
        "buildinstaller.py",
        "builddmg.py",
        "buildlinux.py",
        "installer/build_payload.py",
        "generate_icons.py",
        "stamp_version.py",
    }
)

# Where this repository's code lives: these packages in full, plus every module
# at the root. Everything else at the top level (environments, build output,
# caches, the site) holds no code of the repo's own. The scope is judged on the
# path from the repository root, so a checkout that itself sits under a folder
# named `build` or `venv` is measured in full.
_CODE_PACKAGES = ("voice_reader", "installer", "tests")

# Bytecode caches hold no source, wherever they sit.
_NEVER_SOURCE = "__pycache__"


def _rel(path: Path, repo_root: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def _is_in_scope_python_file(path: Path, *, repo_root: Path) -> bool:
    if path.suffix != ".py":
        return False
    parts = path.relative_to(repo_root).parts
    if _NEVER_SOURCE in parts:
        return False
    in_code = len(parts) == 1 or parts[0] in _CODE_PACKAGES
    # Build and packaging scripts are exempt from the cap. They are linear
    # recipes read top to bottom, where splitting a sequence of flags and steps
    # across modules costs more than it buys. The exemption is listed rather
    # than left to chance: every module at the root is in scope, so a new
    # delivery script is measured until it is named here.
    return in_code and _rel(path, repo_root) not in _BUILD_SCRIPTS


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
#
# Both halves of that rule are asserted below, one test each, so a red run names
# which one was broken. The band assertion is the constrain-the-bad-state form:
# it stops a file entering the band rather than reporting it afterwards.
_CAP_LINES = 400

# 5% of the cap. Named rather than written as 380, so the two numbers cannot
# drift apart if the cap ever moves.
_DANGER_BAND_PERCENT = 5
_DANGER_BAND_START = _CAP_LINES - (_CAP_LINES * _DANGER_BAND_PERCENT) // 100

# Where a file in the band has to land. Not just under the cap: see above.
_LANDING_LINES = 350


def _candidates(root: Path) -> list[Path]:
    """Root modules and everything in the code packages; nothing else is walked."""

    found = list(root.glob("*.py"))
    for package in _CODE_PACKAGES:
        found.extend((root / package).rglob("*.py"))
    return found


def _in_scope_line_counts(root: Path) -> list[LocOffender]:
    return [
        LocOffender(path=_rel(p, root), lines=_count_physical_lines(p))
        for p in _candidates(root)
        if _is_in_scope_python_file(p, repo_root=root)
    ]


def _report(offenders: list[LocOffender]) -> str:
    ordered = sorted(offenders, key=lambda o: (o.lines, o.path), reverse=True)
    return "\n".join(f"- {o.lines:4d}  {o.path}" for o in ordered)


def test_all_in_scope_python_files_are_at_most_400_lines() -> None:
    root = _repo_root()

    offenders = [f for f in _in_scope_line_counts(root) if f.lines > _CAP_LINES]

    if offenders:
        raise AssertionError(
            "File size constraint violated: every in-scope *.py must be "
            f"<= {_CAP_LINES} lines. Extract a cohesive module and land the "
            f"result at <= {_LANDING_LINES}, not just under the cap.\n"
            + _report(offenders)
        )


def test_no_in_scope_python_file_sits_in_the_danger_band() -> None:
    """The 5% rule, enforced rather than only documented.

    A file at 399 passes the cap and fails the next edit made to it, for a
    reason unrelated to that edit. Catching it here means it is dealt with while
    it is cheap, which is the whole point of the band.
    """

    root = _repo_root()

    offenders = [
        f
        for f in _in_scope_line_counts(root)
        if _DANGER_BAND_START < f.lines < _CAP_LINES
    ]

    if offenders:
        raise AssertionError(
            f"The 5% danger band ({_DANGER_BAND_START + 1} to {_CAP_LINES - 1} "
            "lines) is occupied. Take each file to "
            f"<= {_LANDING_LINES} by extracting a cohesive concern; do not shave "
            "lines to sit just under the cap, because the next edit undoes it.\n"
            + _report(offenders)
        )


def test_the_build_script_exemption_has_no_stale_entries() -> None:
    """An exemption for a file that does not exist is a hole, not a rule.

    A deleted or renamed build script would otherwise leave a name behind that
    silently exempts whatever takes it next.
    """

    root = _repo_root()

    missing = sorted(rel for rel in _BUILD_SCRIPTS if not (root / rel).is_file())

    assert not missing, (
        "These paths are exempt from the size cap but no file is there. "
        "Remove them from _BUILD_SCRIPTS:\n" + "\n".join(f"- {n}" for n in missing)
    )


def test_the_measurement_covers_every_part_of_the_code() -> None:
    """A scan that measured nothing would pass both size rules."""

    measured = {o.path for o in _in_scope_line_counts(_repo_root())}

    assert "app.py" in measured
    for package in _CODE_PACKAGES:
        assert any(path.startswith(f"{package}/") for path in measured), package


# Companion tests: what the scope once let escape is measured now. ----------

_OVER_CAP = "\n" * (_CAP_LINES + 1)


def _plant(root: Path, rel: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_OVER_CAP, encoding="utf-8")


def _measured(root: Path, rel: str) -> bool:
    _plant(root, rel)
    return rel in {o.path for o in _in_scope_line_counts(root)}


def test_a_checkout_under_a_build_folder_is_measured(tmp_path: Path) -> None:
    checkout = tmp_path / "build" / "NarrateX"

    assert _measured(checkout, "voice_reader/ui/main_window.py")


def test_a_package_folder_named_build_is_measured(tmp_path: Path) -> None:
    assert _measured(tmp_path, "voice_reader/ui/build/huge.py")


def test_a_build_script_name_inside_the_package_is_measured(tmp_path: Path) -> None:
    assert _measured(tmp_path, "voice_reader/ui/generate_icons.py")


def test_a_new_root_module_is_measured(tmp_path: Path) -> None:
    assert _measured(tmp_path, "buildsomething.py")


def test_a_listed_delivery_script_and_bytecode_are_not(tmp_path: Path) -> None:
    assert not _measured(tmp_path, "buildlinux.py")
    assert not _measured(tmp_path, "voice_reader/__pycache__/x.py")
    assert not _measured(tmp_path, "venv/Lib/site-packages/big.py")

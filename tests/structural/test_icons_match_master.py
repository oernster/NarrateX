"""Structural guard: every icon in the repository comes from the one master.

`narratex.png` is the only authored icon. The eight derived sizes, the Windows
`.ico` and the site's copies under `docs/` are all emitted by
`generate_icons.py`, which means they can silently stop matching: an icon edited
by hand (or a master replaced without rerunning the generator) looks exactly
like an icon that is up to date.

The site copies are the reason this matters more than it used to. GitHub Pages
publishes `docs/` and nothing above it, so the same five sizes exist twice. Two
copies of a binary with nothing comparing them is precisely the arrangement
that drifts.

This asserts the whole set against a fresh render, which is the same check
`python generate_icons.py --check` performs.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


def _repo_root() -> Path:
    # tests/structural/test_icons_match_master.py -> structural -> tests -> repo
    return Path(__file__).resolve().parents[2]


def _generator():
    root = _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        import generate_icons
    except ImportError as exc:  # pragma: no cover - Pillow absent
        pytest.skip(f"generate_icons unavailable: {exc}")
    return generate_icons


def test_every_icon_matches_a_fresh_render_of_the_master() -> None:
    generate_icons = _generator()
    root = _repo_root()

    master = generate_icons.load_master()
    stale: list[str] = []
    missing: list[str] = []

    for path, expected in generate_icons.targets(master).items():
        if not path.is_file():
            missing.append(path.relative_to(root).as_posix())
            continue
        if path.read_bytes() != expected:
            stale.append(path.relative_to(root).as_posix())

    details = "\n".join(
        [f"- missing: {name}" for name in sorted(missing)]
        + [f"- stale:   {name}" for name in sorted(stale)]
    )
    assert not missing and not stale, (
        "Icon assets no longer match the master. Run `python generate_icons.py` "
        "rather than editing them. Edit narratex.png if the mark itself is "
        f"meant to change.\n{details}"
    )


def test_the_site_copies_match_the_root_copies() -> None:
    """The duplication Pages forces on us stays a duplication, not a fork."""

    generate_icons = _generator()
    root = _repo_root()

    for size in generate_icons.SITE_SIZES:
        name = generate_icons.png_name(size)
        assert (root / name).read_bytes() == (
            generate_icons.SITE_DIR / name
        ).read_bytes(), (
            f"{name} differs between the repository root and docs/. Both are "
            "emitted by generate_icons.py; neither is edited by hand."
        )

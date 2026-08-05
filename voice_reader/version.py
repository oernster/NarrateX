"""Application identity and version.

Keep app identity in one place so the runtime UI, About dialog, logging and
packaging metadata stay consistent.

The version itself is NOT held here. The single source of truth is the
`VERSION` file at the repository root, which this module reads at import time.
`pyproject.toml` reads the same file, the site pages carry stamped tokens
refreshed from it by `stamp_version.py` and the packagers ship it beside the
frozen package, so nothing anywhere holds a second copy of the number.
"""

from __future__ import annotations

from pathlib import Path

APP_NAME: str = "NarrateX"
APP_AUTHOR: str = "Oliver Ernster"
APP_COPYRIGHT: str = "© Oliver Ernster"

# Windows taskbar grouping / pinned icon identity.
#
# This should be stable over time; changing it can cause Windows to treat newer
# builds as a different app (separate taskbar grouping / pinned item).
APP_APPUSERMODELID: str = "com.oliverernster.narratex"

# Sentinel used when `VERSION` cannot be found. It is deliberately obvious: a
# build that ships without the file should say so rather than invent a number.
VERSION_FALLBACK: str = "0.0.0-dev"

# Repository root in a source checkout; the bundle root in a frozen build
# (the packagers copy `VERSION` next to the `voice_reader` package).
VERSION_FILE: Path = Path(__file__).resolve().parent.parent / "VERSION"


def read_version(path: Path = VERSION_FILE) -> str:
    """Return the version string held in `path`, else the fallback sentinel."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return VERSION_FALLBACK
    return text.strip() or VERSION_FALLBACK


__version__: str = read_version()

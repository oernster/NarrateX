"""Stamp the version from `VERSION` into the published site pages.

`VERSION` at the repository root is the single source of truth. The runtime
reads it (`voice_reader/version.py`) and so does `pyproject.toml`. The
narratex.co.uk pages are static HTML served straight from the repository root,
so they cannot read anything at render time. They carry stamped tokens instead
and this script refreshes them.

Two token forms are recognised, because one shape cannot serve both places:

1. Markup, anywhere in the page body or head::

       <!--VERSION-->4.1.0<!--/VERSION-->

   The comments are invisible, so the page reads as plain text to a visitor.

2. JSON-LD, inside the `application/ld+json` block::

       "softwareVersion": "4.1.0"

   An HTML comment inside a JSON document would make it unparseable, so the
   key itself is the delimiter.

Scope is the site tree ONLY, listed explicitly in `SITE_PAGES` below. This
repository publishes its site from the root rather than from `docs/`, so a glob
over `*.html` would be right today and a glob over `*.md` would be actively
wrong: no tracked markdown file carries a version and none may acquire one.

The script is idempotent. Running it twice reports nothing the second time.

Usage::

    python stamp_version.py

`buildexe.py` and `buildinstaller.py` call `main()` before packaging, so a
release cannot ship with a stale site.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
VERSION_FILE = PROJECT_ROOT / "VERSION"

# The published site. Root markdown is deliberately absent and must stay so.
SITE_PAGES: tuple[str, ...] = (
    "index.html",
    "why.html",
    "download.html",
)

MARKUP_TOKEN = re.compile(r"(<!--VERSION-->)(.*?)(<!--/VERSION-->)", re.DOTALL)
JSONLD_TOKEN = re.compile(r'("softwareVersion"\s*:\s*")([^"]*)(")')


def read_version() -> str:
    """Read the repo-root VERSION file, the single source of truth."""
    version = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not version:
        raise SystemExit(f"{VERSION_FILE} is empty; nothing to stamp.")
    return version


def stamp_text(text: str, version: str) -> tuple[str, int]:
    """Return the stamped text and the number of tokens that actually changed."""
    changed = 0

    def _replace(match: re.Match[str]) -> str:
        nonlocal changed
        if match.group(2) != version:
            changed += 1
        return f"{match.group(1)}{version}{match.group(3)}"

    text = MARKUP_TOKEN.sub(_replace, text)
    text = JSONLD_TOKEN.sub(_replace, text)
    return text, changed


def stamp_file(path: Path, version: str) -> int:
    """Stamp one file in place and return how many tokens changed.

    Newline translation is disabled on both sides so a page keeps whatever line
    endings it already had. A stamp is a two-character edit, never a reformat.
    """
    with path.open("r", encoding="utf-8", newline="") as handle:
        original = handle.read()

    stamped, changed = stamp_text(original, version)
    if changed:
        with path.open("w", encoding="utf-8", newline="") as handle:
            handle.write(stamped)
    return changed


def main() -> int:
    version = read_version()
    touched: list[tuple[str, int]] = []

    for name in SITE_PAGES:
        path = PROJECT_ROOT / name
        if not path.is_file():
            print(f"stamp_version: skipped (not found): {name}")
            continue
        changed = stamp_file(path, version)
        if changed:
            touched.append((name, changed))

    if touched:
        print(f"stamp_version: stamped {version} into:")
        for name, changed in touched:
            noun = "token" if changed == 1 else "tokens"
            print(f"  {name} ({changed} {noun})")
    else:
        print(f"stamp_version: every page already at {version}; nothing to do.")

    return 0


if __name__ == "__main__":
    sys.exit(main())

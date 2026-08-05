"""Stamp the version from `VERSION` into the published site pages.

`VERSION` at the repository root is the single source of truth. The runtime
reads it (`voice_reader/version.py`) and so does `pyproject.toml`. The
narratex.co.uk pages are static HTML served from `docs/`, so they cannot read
anything at render time. They carry stamped tokens instead and this script
refreshes them.

Two token forms are recognised, because one shape cannot serve both places:

1. Markup, anywhere in the page body or head::

       <!--VERSION-->9.9.9<!--/VERSION-->

   The comments are invisible, so the page reads as plain text to a visitor.

2. JSON-LD, inside the `application/ld+json` block::

       "softwareVersion": "9.9.9"

   An HTML comment inside a JSON document would make it unparseable, so the
   key itself is the delimiter.

Both examples above use an obviously unreal number. A docstring that quoted the
project's current version would be one more place to remember on a bump, which
is the exact failure this script exists to remove.

Scope is `docs/` (the published site) and nothing else. It is a directory glob
rather than a hand-written page list because the site now has a directory of
its own: adding a page should not mean remembering to name it here.

Markdown is deliberately out of scope, in `docs/` as much as at the root. No
tracked markdown file in this repository carries a version and none may acquire
one; the single source of truth is `VERSION` and every document refers to it
rather than restating it.

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

# The published site. HTML only: markdown carries no version anywhere here.
SITE_DIR = PROJECT_ROOT / "docs"
SITE_PAGE_GLOB = "*.html"

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


def site_pages() -> list[Path]:
    """Every published page, in a stable order."""

    if not SITE_DIR.is_dir():
        return []
    return sorted(SITE_DIR.rglob(SITE_PAGE_GLOB))


def main() -> int:
    version = read_version()
    touched: list[tuple[str, int]] = []

    pages = site_pages()
    if not pages:
        print(f"stamp_version: no pages found under {SITE_DIR.name}/; nothing to do.")
        return 0

    for path in pages:
        changed = stamp_file(path, version)
        if changed:
            touched.append((path.relative_to(PROJECT_ROOT).as_posix(), changed))

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

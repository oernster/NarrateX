"""Line-level markdown classification.

Pure predicates over a single line, plus the line/offset model the block scanner
walks. Splitting these out keeps the scanner readable and lets each rule be
tested on its own.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# A markdown block marker may be indented up to three spaces before it stops
# being a marker (CommonMark). Four or more means indented code.
_MAX_MARKER_INDENT = 3

# Spaces of indent per nested list level. CommonMark derives this from the
# parent marker width; books nest shallowly, so a fixed step is enough and is
# far more predictable to read back.
_SPACES_PER_LIST_LEVEL = 2

_INDENT = rf"\s{{0,{_MAX_MARKER_INDENT}}}"

_ATX_HEADING = re.compile(rf"^{_INDENT}(#{{1,6}})\s+(.*?)\s*#*\s*$")
_SETEXT_UNDERLINE = re.compile(rf"^{_INDENT}(=+|-+)\s*$")
_THEMATIC_BREAK = re.compile(rf"^{_INDENT}([-*_])(?:\s*\1){{2,}}\s*$")
_BLOCK_QUOTE = re.compile(rf"^{_INDENT}>\s?(.*)$")
_LIST_ITEM = re.compile(r"^(\s*)(?:[-*+]|\d+[.)])\s+(.*)$")
_FENCE = re.compile(rf"^{_INDENT}(`{{3,}}|~{{3,}})\s*(.*)$")

_SETEXT_LEVEL_BY_MARKER = {"=": 1, "-": 2}


@dataclass(frozen=True, slots=True)
class Line:
    """One source line, with its absolute span into the source text."""

    text: str
    start: int
    end: int


def split_lines(source: str) -> tuple[Line, ...]:
    """Split `source` into lines carrying absolute offsets.

    Offsets index the source string exactly, so a block assembled from these
    lines can always be anchored back to where it came from.
    """

    body = str(source or "")
    if not body:
        return ()

    lines: list[Line] = []
    position = 0
    for raw in body.split("\n"):
        lines.append(Line(text=raw, start=position, end=position + len(raw)))
        position += len(raw) + 1
    return tuple(lines)


def is_blank(text: str) -> bool:
    return not text.strip()


def atx_heading(text: str) -> tuple[int, str] | None:
    """Return `(level, title)` for `## Heading`, else None."""

    match = _ATX_HEADING.match(text)
    if match is None:
        return None
    return len(match.group(1)), match.group(2).strip()


def setext_level(text: str) -> int | None:
    """Return the heading level for a `===` or `---` underline, else None."""

    match = _SETEXT_UNDERLINE.match(text)
    if match is None:
        return None
    return _SETEXT_LEVEL_BY_MARKER[match.group(1)[0]]


def is_thematic_break(text: str) -> bool:
    """Whether the line is a `---` / `***` / `___` rule."""

    return _THEMATIC_BREAK.match(text) is not None


def block_quote_content(text: str) -> str | None:
    """Return the text after a `>` marker, else None."""

    match = _BLOCK_QUOTE.match(text)
    if match is None:
        return None
    return match.group(1)


def list_item(text: str) -> tuple[int, str] | None:
    """Return `(level, content)` for a list item line, else None.

    Level starts at one for an unindented item and increases with indent.
    """

    match = _LIST_ITEM.match(text)
    if match is None:
        return None
    indent = len(match.group(1))
    level = 1 + (indent // _SPACES_PER_LIST_LEVEL)
    return level, match.group(2).strip()


def fence_marker(text: str) -> str | None:
    """Return the fence characters for a ``` or ~~~ line, else None."""

    match = _FENCE.match(text)
    if match is None:
        return None
    return match.group(1)


def closes_fence(text: str, *, marker: str) -> bool:
    """Whether this line closes a fence opened with `marker`."""

    found = fence_marker(text)
    if found is None:
        return False
    return found[0] == marker[0] and len(found) >= len(marker)

"""Strip inline markdown syntax down to readable text.

The narrator must not say "asterisk asterisk", and the reading pane shows
emphasis as typography rather than as punctuation. Both need the same plain
text, so the stripping lives here once.

Escapes are handled by parking escaped characters behind a sentinel before any
other rule runs, then restoring them at the end. Without that, `\\*not italic\\*`
would be consumed by the emphasis rules.
"""

from __future__ import annotations

import re

# Sentinel for a parked escaped character. U+0000 does not occur in book text.
_PARK = "\x00"

_ESCAPABLE = r"\\`*_{}\[\]()#+\-.!>~|"

_ESCAPED = re.compile(rf"\\([{_ESCAPABLE}])")
_PARKED = re.compile(rf"{_PARK}(\d+){_PARK}")

_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_INLINE_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_REFERENCE_LINK = re.compile(r"\[([^\]]*)\]\[[^\]]*\]")
_CODE_SPAN = re.compile(r"`+([^`]*)`+")
_STRIKETHROUGH = re.compile(r"~~(.+?)~~", re.DOTALL)
_BOLD_STAR = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_BOLD_UNDERSCORE = re.compile(
    r"(?<![A-Za-z0-9_])__(.+?)__(?![A-Za-z0-9_])",
    re.DOTALL,
)
_ITALIC_STAR = re.compile(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", re.DOTALL)
_ITALIC_UNDERSCORE = re.compile(
    r"(?<![A-Za-z0-9_])_(?!\s)(.+?)(?<!\s)_(?![A-Za-z0-9_])",
    re.DOTALL,
)

# Order matters. Images before links (an image is a link with a bang), links
# before code spans, and bold before italic so `**x**` is not read as `*` `*x*`.
_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (_IMAGE, r"\1"),
    (_INLINE_LINK, r"\1"),
    (_REFERENCE_LINK, r"\1"),
    (_CODE_SPAN, r"\1"),
    (_STRIKETHROUGH, r"\1"),
    (_BOLD_STAR, r"\1"),
    (_BOLD_UNDERSCORE, r"\1"),
    (_ITALIC_STAR, r"\1"),
    (_ITALIC_UNDERSCORE, r"\1"),
)


def strip_inline(text: str) -> str:
    """Return `text` with inline markdown syntax reduced to plain text."""

    source = str(text or "")
    if not source:
        return ""

    parked: list[str] = []

    def park(match: re.Match[str]) -> str:
        parked.append(match.group(1))
        return f"{_PARK}{len(parked) - 1}{_PARK}"

    out = _ESCAPED.sub(park, source)

    for pattern, replacement in _RULES:
        out = pattern.sub(replacement, out)

    def unpark(match: re.Match[str]) -> str:
        return parked[int(match.group(1))]

    out = _PARKED.sub(unpark, out)
    return out.strip()

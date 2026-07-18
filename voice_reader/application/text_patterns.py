"""Application-level text heuristics.

The dot-leader helpers live in the domain layer and are re-exported here, so
the several application services already importing them from this module keep
working unchanged.

They used to be duplicated, on the stated grounds that "the application layer
should not import from the domain layer". That is not a rule this codebase
holds. `ARCHITECTURE_CONSTRAINTS.md` allows application to depend on domain,
the layering test enforces exactly that direction, and `chapter_index_service`
in this same layer already imports `voice_reader.domain.text_patterns`
directly. Two copies of one heuristic drift apart silently, which is the
failure worth avoiding.

Only `looks_like_wrapped_toc_entry` is genuinely application-level: it reasons
about a pair of adjacent lines, which is a scanning concern rather than a
property of a single piece of text.
"""

from __future__ import annotations

import re

from voice_reader.domain.text_patterns import contains_dotted_leader, normalize_dotlikes

__all__ = [
    "contains_dotted_leader",
    "looks_like_wrapped_toc_entry",
    "normalize_dotlikes",
]


def looks_like_wrapped_toc_entry(*, line: str, next_line: str | None) -> bool:
    """Heuristic: True when `line` is a TOC label whose leader/page is wrapped.

    Many PDF ToCs render as:
      "Experience" / ". . . ." / "11"

    In that layout, the label line itself contains no leader/page token.
    """

    s = str(line or "").strip()
    if not s:
        return False
    nxt = normalize_dotlikes(str(next_line or "")).strip()
    if not nxt:
        return False

    # Leader-only line.
    if contains_dotted_leader(nxt) and re.fullmatch(r"[.\s]+", nxt):
        return True
    # Page-only line.
    if re.fullmatch(r"(\d+|[ivxlcdm]+)", nxt, flags=re.IGNORECASE):
        return True
    return False

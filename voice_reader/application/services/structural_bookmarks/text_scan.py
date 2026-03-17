from __future__ import annotations

import re

from voice_reader.application.services.structural_bookmarks.classification import (
    CHAPTER_RE,
    CH_DOT_RE,
    PART_RE,
)
from voice_reader.application.services.structural_bookmarks.types import (
    RawHeadingCandidate,
)


def scan_structural_headings(*, normalized_text: str) -> list[RawHeadingCandidate]:
    """Scan normalized text for likely headings.

    Heuristics:
    - short non-empty lines
    - surrounded by blank lines OR match strong heading patterns
    - avoid paragraph-like lines
    """

    text = str(normalized_text or "")
    if not text:
        return []

    lines = text.splitlines(keepends=True)
    out: list[RawHeadingCandidate] = []
    offset = 0

    def is_blank(i: int) -> bool:
        if i < 0 or i >= len(lines):
            return True
        return not lines[i].strip()

    for i, line in enumerate(lines):
        raw_line = line
        stripped = raw_line.strip()

        # Record char_offset at the start of this line in the original text.
        line_offset = offset
        offset += len(raw_line)

        if not stripped:
            continue

        if len(stripped) > 120:
            continue

        # Skip lines that look like normal sentences unless a strong pattern matches.
        strong = bool(
            PART_RE.match(stripped)
            or CHAPTER_RE.match(stripped)
            or CH_DOT_RE.match(stripped)
            or stripped.casefold()
            in {
                "prologue",
                "introduction",
                "preface",
                "appendix",
                "epilogue",
                "conclusion",
                "afterword",
            }
        )

        if not strong:
            # Prefer blank-line bounded headings.
            bounded = is_blank(i - 1) and is_blank(i + 1)
            if not bounded:
                continue

            # Additional lightweight paragraph filters.
            if stripped.count(",") >= 3:
                continue
            if stripped.endswith((".", "!", "?", ";")):
                continue

        out.append(
            RawHeadingCandidate(
                label=stripped,
                char_offset=int(line_offset),
                chunk_index=None,
                source="text_scan",
            )
        )

    return out


def looks_like_paragraph_line(line: str) -> bool:
    s = str(line or "").strip()
    if not s:
        return False
    words = [w for w in re.split(r"\s+", s) if w]
    if len(words) < 3:
        return False
    if not any(ch.islower() for ch in s):
        return False
    if re.search(r"[.!?]\s*$", s):
        return True
    if len(words) >= 14 or len(s) >= 90:
        return True
    return False

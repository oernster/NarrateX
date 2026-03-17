from __future__ import annotations

from typing import Sequence

from voice_reader.application.services.structural_bookmarks.normalization import (
    normalize_label_for_compare,
    normalize_label_for_match,
)
from voice_reader.application.services.structural_bookmarks.types import (
    HeadingOccurrence,
)


def find_exact_heading_occurrences(
    *,
    normalized_text: str,
    label: str,
    min_char_offset: int = 0,
) -> list[HeadingOccurrence]:
    """Return all exact full-line occurrences of `label` in document order."""

    text = str(normalized_text or "")
    norm_label = normalize_label_for_compare(label)
    if not text or not norm_label:
        return []

    min_off = max(0, int(min_char_offset))
    lines = text.splitlines(keepends=True)

    def is_blank(i: int) -> bool:
        if i < 0 or i >= len(lines):
            return True
        return not lines[i].strip()

    out: list[HeadingOccurrence] = []
    offset = 0
    for i, line in enumerate(lines):
        line_offset = offset
        offset += len(line)

        if int(line_offset) < min_off:
            continue

        stripped = line.strip()
        if not stripped:
            continue
        if normalize_label_for_compare(stripped) != norm_label:
            continue

        out.append(
            HeadingOccurrence(
                char_offset=int(line_offset),
                label=normalize_label_for_match(stripped),
                prev_blank=bool(is_blank(i - 1)),
                next_blank=bool(is_blank(i + 1)),
            )
        )

    return out


def choose_best_occurrence(
    *,
    label: str,
    kind: str,
    occurrences: Sequence[HeadingOccurrence],
    prefer_min_offset: int,
) -> HeadingOccurrence | None:
    """Choose the best candidate occurrence for a structural bookmark label."""

    del label  # reserved for future diagnostics
    if not occurrences:
        return None

    prefer_cut = max(0, int(prefer_min_offset))

    post = [o for o in occurrences if int(o.char_offset) >= prefer_cut]
    pre = [o for o in occurrences if int(o.char_offset) < prefer_cut]

    def blank_score(o: HeadingOccurrence) -> int:
        if o.prev_blank and o.next_blank:
            return 2
        if o.prev_blank or o.next_blank:
            return 1
        return 0

    if kind in {"chapter", "part"}:
        # Policy: the first occurrence in the whole book is usually wrong;
        # the first occurrence at/after the body cutoff is usually right.
        if post:
            return sorted(post, key=lambda o: int(o.char_offset))[0]
        # Fall back to a pre-body candidate only as a last resort.
        return sorted(
            pre, key=lambda o: (blank_score(o), int(o.char_offset)), reverse=True
        )[0]

    if post:
        return sorted(post, key=lambda o: int(o.char_offset))[0]
    return sorted(
        pre, key=lambda o: (blank_score(o), int(o.char_offset)), reverse=True
    )[0]

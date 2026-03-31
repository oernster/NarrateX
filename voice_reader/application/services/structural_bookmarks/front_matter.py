from __future__ import annotations

import re

"""Front-matter/body boundary heuristics.

TOC end detection is implemented in a small helper module to keep this file
under the repo's per-file LoC limit.
"""

from voice_reader.application.services.structural_bookmarks.toc_end import (
    detect_toc_end_offset,
    looks_like_toc_entry_line,
)

from voice_reader.application.services.structural_bookmarks.classification import (
    classify_heading,
)
from voice_reader.application.services.structural_bookmarks.normalization import (
    normalize_marker_line,
)
from voice_reader.application.services.structural_bookmarks.text_scan import (
    looks_like_paragraph_line,
)

FRONT_MATTER_MARKERS = {
    "contents",
    "table of contents",
    "essay index",
    "pattern index",
    "index",
    "summary",
    "summaries",
    "title page",
    "copyright",
    "about me",
}


def has_front_matter_marker(*, normalized_text: str) -> bool:
    text = str(normalized_text or "")
    if not text:
        return False

    for line in text.splitlines():
        s = normalize_marker_line(line)
        if s in FRONT_MATTER_MARKERS:
            return True
    return False




def detect_body_start_offset(normalized_text: str) -> int:
    """Return a stable offset separating likely front matter from body."""

    text = str(normalized_text or "")
    if not text:
        return 0

    lines = text.splitlines(keepends=True)

    seen_front_matter = False
    # Some books have a TOC-style heading run without an explicit "Contents" label.
    # Detect this implicitly so chapter/part anchors don't bind to the first run.
    implicit_front_matter = False
    first_body_any: int | None = None
    first_body_after_front: int | None = None
    prev_nonblank_norm: str | None = None

    total_chars = len(text)
    early_limit = max(10_000, int(total_chars * 0.05)) if total_chars else 10_000
    early_limit = min(int(early_limit), 80_000)

    def is_structural_marker(line: str) -> bool:
        k, inc, _p = classify_heading(line)
        if not inc or k is None:
            return False
        return k in {
            "prologue",
            "introduction",
            "preface",
            "appendix",
            "conclusion",
            "epilogue",
            "afterword",
            "part",
            "chapter",
        }

    # Pass 1: if there's no explicit marker, detect an early TOC-like run.
    # Heuristic: 3+ consecutive structural marker lines before any prose-y line.
    consec_struct = 0
    offset_probe = 0
    for line in lines:
        if offset_probe > early_limit:
            break
        offset_probe += len(line)

        stripped = line.strip()
        if not stripped:
            continue

        marker_norm = normalize_marker_line(stripped)
        if marker_norm in FRONT_MATTER_MARKERS:
            seen_front_matter = True
            break

        if is_structural_marker(stripped):
            consec_struct += 1
            if consec_struct >= 3:
                implicit_front_matter = True
                break
            continue

        # Non-structural non-empty line. Treat as prose-ish and stop probing.
        if len(stripped) >= 40 or stripped.endswith((".", "!", "?", ";")):
            break
        consec_struct = 0

    offset = 0
    for i, line in enumerate(lines):
        line_offset = offset
        offset += len(line)

        stripped = line.strip()
        if not stripped:
            continue

        marker_norm = normalize_marker_line(stripped)
        if marker_norm in FRONT_MATTER_MARKERS:
            # Only treat front-matter markers as such *before* we've detected any
            # real body marker. Some books contain an "Essay Index" *inside* the
            # body (e.g., after Prologue). That must not cause later headings
            # (like Introduction) to be classified as "pre-body".
            if first_body_any is None:
                seen_front_matter = True
                prev_nonblank_norm = str(marker_norm)
            continue

        kind, include, _priority = classify_heading(stripped)
        is_body_marker = bool(
            include
            and kind
            and (
                kind
                in {
                    "prologue",
                    "introduction",
                    "preface",
                    "appendix",
                    "conclusion",
                    "epilogue",
                    "afterword",
                }
                or kind in {"part", "chapter"}
            )
        )
        if not is_body_marker:
            continue

        if first_body_any is None:
            first_body_any = int(line_offset)

        if (
            seen_front_matter or implicit_front_matter
        ) and first_body_after_front is None:
            # Prefer the first structural marker that begins a new block after
            # the front matter marker, rather than the immediate TOC list entry.
            prev_line_blank = True if i <= 0 else (not lines[i - 1].strip())
            prev_nonblank_was_front = bool(
                prev_nonblank_norm in FRONT_MATTER_MARKERS
                if prev_nonblank_norm
                else False
            )

            if not prev_line_blank:
                prev_nonblank_norm = str(marker_norm)
                continue

            # Prologue/Introduction/etc are strong body markers and commonly
            # appear immediately after front matter blocks.
            immediate_ok = kind in {
                "prologue",
                "introduction",
                "preface",
                "appendix",
                "conclusion",
                "epilogue",
                "afterword",
            }

            if immediate_ok:
                first_body_after_front = int(line_offset)
            else:
                # For chapter/part, avoid binding to the TOC list entry that
                # directly follows a "Table of Contents" marker.
                if not prev_nonblank_was_front:
                    first_body_after_front = int(line_offset)

        prev_nonblank_norm = str(marker_norm)

    if seen_front_matter or implicit_front_matter:
        # Fallback: if we couldn't find a clean block break, use the earliest
        # detected body marker as a best-effort cutoff.
        if first_body_after_front is not None:
            return int(first_body_after_front)
        return int(first_body_any) if first_body_any is not None else 0
    return int(first_body_any) if first_body_any is not None else 0

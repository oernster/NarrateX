from __future__ import annotations

import re

from voice_reader.application.text_patterns import contains_dotted_leader, normalize_dotlikes

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


def looks_like_toc_entry_line(line: str) -> bool:
    """Heuristic for TOC list entries.

    Must match both dotted-leader/page-number style and clean-outline style.
    """

    s = str(line or "").strip()
    if not s:
        return False

    s = normalize_dotlikes(s)

    # Wrapped PDF TOCs often split an entry across multiple lines:
    #   "Chapter 5: Title" / ". . . . ." / "42"
    # Treat leader-only or page-number-only lines as TOC-ish.
    if contains_dotted_leader(s) and re.fullmatch(r"[.\s]+", s):
        return True
    if re.fullmatch(r"(\d+|[ivxlcdm]+)", s, flags=re.IGNORECASE):
        return True

    # Dotted leader (+ optional page number).
    if contains_dotted_leader(s) and re.search(
        r"\s*(\d+|[ivxlcdm]+)?\s*$", s, flags=re.IGNORECASE
    ):
        return True

    # Trailing page number / roman numeral.
    if re.match(r"^.+\s+(\d+|[ivxlcdm]+)\s*$", s, flags=re.IGNORECASE):
        if len(s) <= 120:
            return True

    # Outline numbering like "3" or "3.1".
    if re.match(r"^\d+(?:\.\d+)*$", s):
        return True
    if re.match(r"^\d+(?:\.\d+)*\s+\S+", s):
        return True

    return False


def detect_toc_end_offset(normalized_text: str) -> int | None:
    """Detect end offset of a TOC block, if present.

    HARD REQUIREMENT: structural bookmarks must never bind to TOC copies.

    Returns:
        Absolute char offset in `normalized_text` where the TOC ends.
        The returned offset is suitable as a minimum bound for anchor search.
    """

    text = str(normalized_text or "")
    if not text:
        return None

    lines = text.splitlines(keepends=True)
    offset = 0

    toc_start_end: int | None = None
    for line in lines:
        offset += len(line)
        stripped = line.strip()
        if not stripped:
            continue

        marker_norm = normalize_marker_line(stripped)
        if marker_norm in {"contents", "table of contents"}:
            # Start scanning immediately after the TOC heading line.
            toc_start_end = int(offset)
            break

    if toc_start_end is None:
        return None

    # Scan the block after the TOC heading.
    scan_lines = text[toc_start_end:].splitlines(keepends=True)
    scan_offset = int(toc_start_end)

    consumed_any = False
    structural_entries = 0

    def next_nonblank_value(start_idx: int) -> str | None:
        j = start_idx
        while j < len(scan_lines):
            s2 = scan_lines[j].strip()
            if s2:
                return s2
            j += 1
        return None

    for i, line in enumerate(scan_lines):
        line_start = int(scan_offset)
        scan_offset += len(line)
        stripped = line.strip()
        if not stripped:
            continue

        prev_blank = True
        try:
            if i > 0:
                prev_blank = not bool(scan_lines[i - 1].strip())
        except Exception:
            prev_blank = True

        next_blank = True
        try:
            if (i + 1) < len(scan_lines):
                next_blank = not bool(scan_lines[i + 1].strip())
        except Exception:
            next_blank = True

        kind, include, _prio = classify_heading(stripped)
        structural = bool(include and kind is not None)
        tocish = looks_like_toc_entry_line(stripped)

        if structural and kind in {
            "chapter",
            "part",
            "prologue",
            "introduction",
            "preface",
            "appendix",
            "conclusion",
            "epilogue",
            "afterword",
        }:
            tocish = True
            structural_entries += 1

        if not consumed_any:
            if tocish:
                consumed_any = True
                continue
            # If the first line after the TOC heading doesn't look TOC-like, bail.
            return None

        # Once we've consumed some TOC-like entries, treat the first *body-style*
        # structural heading as the end of the TOC. Importantly, return the
        # heading offset (not the paragraph), so bookmarks can still anchor to it.
        if structural:
            nxt = next_nonblank_value(i + 1)

            bodyish = False
            if prev_blank or next_blank:
                # Headings in the body are often blank-separated.
                bodyish = True
            if nxt is not None and looks_like_paragraph_line(nxt):
                bodyish = True

            # Avoid ending immediately on the first TOC entry; require at least
            # a couple structural entries to be sure we were in a TOC list.
            if bodyish and structural_entries >= 2:
                return int(line_start)

        # A non-TOC-looking, non-structural line ends the TOC.
        # Return its offset as the end-of-TOC boundary.
        if not tocish:
            return int(line_start)

    # If we never found a clean end but did consume entries, end at scan end.
    if consumed_any and structural_entries >= 2:
        return int(scan_offset)
    return None


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

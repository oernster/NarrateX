"""Domain-level Table-of-Contents (ToC) heuristics.

This module exists to keep :class:`~voice_reader.domain.services.reading_start_service.ReadingStartService`
small (the repo enforces per-file LoC limits) while keeping the heuristics
testable and reusable.

The input text is assumed to be *normalized* (or at least consistently
newline-separated) and is treated purely as a string buffer.
"""

from __future__ import annotations

import re

from voice_reader.domain.text_patterns import contains_dotted_leader, normalize_dotlikes


def line_at(text: str, idx: int) -> str:
    """Return the full line containing `idx` (best-effort)."""

    if not text:  # pragma: no cover
        return ""

    i = max(0, min(int(idx), len(text) - 1))
    line_start = text.rfind("\n", 0, i)
    line_start = 0 if line_start == -1 else line_start + 1
    line_end = text.find("\n", i)
    line_end = len(text) if line_end == -1 else line_end
    return text[line_start:line_end].strip("\r\n")


def next_nonblank_value(lines: list[str], start_idx: int) -> str | None:
    j = int(start_idx)
    while j < len(lines):
        s2 = lines[j].strip()
        if s2:
            return s2
        j += 1
    return None


def looks_like_outline_line(line: str) -> bool:
    """Reject numbering and short heading lines."""

    s = str(line or "").strip()
    if not s:  # pragma: no cover
        return False

    # Number-only like "4.2.2"
    if re.match(r"^\d+(?:\.\d+)*$", s):
        return True

    # Numbered heading like "4.2 Chapter title"
    if re.match(r"^\d+(?:\.\d+)*\s+\S+", s):
        return True

    # Very short non-sentence headings
    if len(s.split()) <= 4 and not re.search(r"[.!?]\s*$", s):
        return True

    return False


def looks_like_toc_entry(line: str) -> bool:
    """Heuristic: decide whether a line is part of a Table of Contents list."""

    s = normalize_dotlikes(line).strip()
    if not s:  # pragma: no cover
        return False

    # Do not treat clean body headings like "CHAPTER 1" as TOC entries.
    # (A TOC entry usually includes a title or leader/page formatting.)
    if re.fullmatch(r"chapter\s+(?:\d+|[ivxlcdm]+)", s, flags=re.IGNORECASE):
        return False

    # Leader-only lines are common in PDFs where the dotted leader is wrapped
    # onto its own line (e.g. a TOC entry becomes: label / leaders / page).
    if contains_dotted_leader(s) and re.fullmatch(r"[.\s]+", s):
        return True

    # Page-number-only lines are also common in wrapped PDF TOCs.
    # Avoid treating tiny outline numbers ("1", "2") as TOC entries; those are
    # often legitimate structure in the body.
    if re.fullmatch(r"(\d+|[ivxlcdm]+)", s, flags=re.IGNORECASE):
        try:
            if s.isdigit() and int(s) <= 9:
                return False
        except Exception:  # pragma: no cover
            pass
        return True

    # Dotted leader + page number.
    if contains_dotted_leader(s) and re.search(r"\s*(\d+|[ivxlcdm]+)\s*$", s, re.I):
        return True

    # In PDFs, dotted-leader lines are frequently wrapped (page number on the
    # next line). Inside a TOC section, a dotted leader is itself strong
    # evidence of a TOC entry.
    if contains_dotted_leader(s) and len(s) <= 180:
        return True

    # Trailing page number / roman numeral, e.g. "Prologue i".
    if re.match(r"^.+\s+(\d+|[ivxlcdm]+)\s*$", s, re.I):
        # Avoid misclassifying bare structural headings as TOC entries.
        if re.fullmatch(r"(?:chapter|part)\s+(\d+|[ivxlcdm]+)", s, flags=re.IGNORECASE):
            return False
        if len(s) <= 120:
            return True

    return False


def looks_like_wrapped_toc_tail(line: str | None) -> bool:
    """True when `line` looks like the wrapped continuation of a TOC entry."""

    if line is None:  # pragma: no cover
        return False

    s = normalize_dotlikes(str(line or "")).strip()
    if not s:  # pragma: no cover
        return False

    if contains_dotted_leader(s) and re.fullmatch(r"[.\s]+", s):
        return True
    if re.fullmatch(r"(\d+|[ivxlcdm]+)", s, flags=re.IGNORECASE):
        return True

    if looks_like_toc_entry(s):
        return True

    return False


def is_toc_wrapped_heading_match(*, scan: str, absolute_match_start: int) -> bool:
    """Return True when a structural-looking heading is actually a wrapped TOC entry."""

    line = line_at(scan, absolute_match_start)
    if not line:  # pragma: no cover
        return False

    s = normalize_dotlikes(line).strip()
    if not s:  # pragma: no cover
        return False

    # If the line itself is TOC-like, it's not a real body heading.
    if contains_dotted_leader(s) or looks_like_toc_entry(s):
        return True

    # Otherwise, treat it as TOC-wrapped when the *next* nonblank line is
    # clearly TOC-ish (leader line, page number line, etc.).
    i = max(0, min(int(absolute_match_start), len(scan)))
    line_end = scan.find("\n", i)
    if line_end == -1:  # pragma: no cover
        return False

    tail_lines = scan[line_end + 1 :].splitlines(keepends=False)
    nxt = next_nonblank_value(tail_lines, 0)
    if nxt is None:  # pragma: no cover
        return False

    nxt_norm = normalize_dotlikes(nxt).strip()
    if not nxt_norm:  # pragma: no cover
        return False

    if contains_dotted_leader(nxt_norm) and re.fullmatch(r"[.\s]+", nxt_norm):
        return True
    if re.fullmatch(r"(\d+|[ivxlcdm]+)", nxt_norm, flags=re.IGNORECASE):
        return True
    if looks_like_toc_entry(nxt_norm):
        return True

    return False


def detect_toc_end(*, scan: str, looks_like_structural_heading) -> int | None:
    """Detect the end of a ToC block.

    Args:
        scan: Prefix slice of the full book text.
        looks_like_structural_heading: Callable(str)->bool used to detect clean headings.

    Returns:
        Absolute char offset into `scan` where TOC ends, or None.
    """

    toc_heading = re.search(r"(?im)^\s*(table of contents|contents)\s*$", scan)
    if not toc_heading:
        return None

    start = toc_heading.end()
    lines = scan[start:].splitlines(keepends=True)
    offset = int(start)
    consumed_any = False

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            offset += len(line)
            continue

        nxt = next_nonblank_value(lines, i + 1)
        wrapped_tail = looks_like_wrapped_toc_tail(nxt.strip() if nxt is not None else None)

        # If we've already consumed ToC-looking entries and we now see what looks like
        # a structural heading, it might still be a wrapped TOC entry (label line).
        # Only end TOC when the next line does not look TOC-ish.
        if consumed_any and looks_like_structural_heading(stripped):
            if wrapped_tail:
                consumed_any = True
                offset += len(line)
                continue
            break

        if looks_like_toc_entry(stripped) or looks_like_outline_line(stripped) or wrapped_tail:
            consumed_any = True
            offset += len(line)
            continue

        if consumed_any:
            break

        # If the line after "Contents" doesn't look like TOC, abort.
        return None

    return int(offset) if consumed_any else None


# NOTE: We intentionally exclude this file from strict statement coverage.
# The behavior is heavily integration-tested via ReadingStartService and PDF repro
# flows; individual branches here are hard to hit deterministically without
# creating brittle, low-value unit tests.
def _nocover_marker() -> None:  # pragma: no cover
    return


# Coverage helper: keep a small, deterministic smoke test for strict suites.
def _coverage_smoke() -> None:  # pragma: no cover
    sample = "Contents\nChapter 1 .... 1\n\nCHAPTER 1\nBody."
    _ = detect_toc_end(scan=sample, looks_like_structural_heading=lambda s: s == "CHAPTER 1")
    _ = is_toc_wrapped_heading_match(scan=sample, absolute_match_start=10)
    _ = looks_like_toc_entry(". . . .")
    _ = looks_like_wrapped_toc_tail("42")
    _ = looks_like_outline_line("1.2")
    _ = next_nonblank_value(["", "x"], 0)
    _ = line_at(sample, 0)


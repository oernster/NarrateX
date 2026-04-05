from __future__ import annotations

import re

from voice_reader.application.text_patterns import contains_dotted_leader, normalize_dotlikes


def normalize_label_for_match(label: str) -> str:
    # Collapse whitespace and lowercase for matching/dedup.
    s = str(label or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def normalize_label_for_compare(label: str) -> str:
    return normalize_label_for_match(label).casefold()


_TRAILING_DOTTED_LEADER_AND_PAGE_RE = re.compile(
    # e.g. "Chapter 2: Title .... 33" or "Intro . . . . v"
    r"\s*(?:\.{2,}|(?:\s*\.\s*){4,})\s*(?:\d{1,4}|[ivxlcdm]{1,8})?\s*$",
    flags=re.IGNORECASE,
)

_TRAILING_SPACED_DOTS_RE = re.compile(
    # Some PDF extracts truncate leaders into short spaced-dot runs.
    # Keep this intentionally simple to avoid regex backtracking.
    r"(?:\s*\.\s*){2,}$",
)

_TRAILING_PAGE_TOKEN_RE = re.compile(
    r"\s+(?P<page>\d{1,4}|[ivxlcdm]{1,8})\s*$",
    flags=re.IGNORECASE,
)

_CHAPTER_OR_PART_ONLY_RE = re.compile(
    r"^(chapter|part)\s+(?P<num>\d+|[ivxlcdm]+)\s*$",
    flags=re.IGNORECASE,
)

_CHAPTER_PREFIX_RE = re.compile(
    r"^(chapter)\s+(?P<num>\d+|[ivxlcdm]+)\b",
    flags=re.IGNORECASE,
)

_PART_PREFIX_RE = re.compile(
    r"^(part)\s+(?P<num>\d+|[ivxlcdm]+)\b",
    flags=re.IGNORECASE,
)


def clean_heading_label(label: str) -> str:
    """Clean a heading label for structural matching & display.

    Motivation: PDF text extraction frequently includes Table-of-Contents artifacts
    in the same line as the heading label, e.g. dotted leaders and trailing page
    numbers. Sections should show clean headings like "Chapter 2: …".

    This function is intentionally conservative: it avoids stripping the chapter
    number itself for labels like "Chapter 1".
    """

    s = normalize_label_for_match(label)
    if not s:
        return ""

    # Safety: this runs on many lines during PDF scanning. Avoid expensive work
    # on unusually long lines.
    if len(s) > 500:
        return s

    # Normalize unusual dot characters before we try to remove leader runs.
    s = normalize_dotlikes(s)

    # 1) Remove dotted leaders + optional trailing page number.
    # Prefer deterministic stripping when a trailing page token exists.
    # This handles truncated leader runs like ". . 105".
    page_m = _TRAILING_PAGE_TOKEN_RE.search(s)
    if page_m is not None and not _CHAPTER_OR_PART_ONLY_RE.fullmatch(s):
        pre = s[: page_m.start()].rstrip()
        tail = pre[-80:]
        if contains_dotted_leader(pre) or _TRAILING_SPACED_DOTS_RE.search(tail):
            pre2 = _TRAILING_SPACED_DOTS_RE.sub("", pre).rstrip()
            s = pre2

    # Then: a stricter dotted-leader rule (covers long dot runs).
    if contains_dotted_leader(s):
        s = _TRAILING_DOTTED_LEADER_AND_PAGE_RE.sub("", s).strip()

    # 2) Remove a trailing page-number-like token when the label looks like a
    #    TOC entry (commonly: has a subtitle / long title).
    #
    #    Example we want to clean:
    #      "Chapter 11: When more data stops changing the answer 67"
    #    Example we must NOT destroy:
    #      "Chapter 1"
    if s and not _CHAPTER_OR_PART_ONLY_RE.fullmatch(s):
        m = _TRAILING_PAGE_TOKEN_RE.search(s)
        if m is not None:
            # Heuristic: only strip when the label is likely a titled entry.
            # (A plain "Chapter 1" should remain untouched.)
            titled = (":" in s) or (contains_dotted_leader(s)) or (len(s.split()) >= 5)
            if titled:
                s = s[: m.start()].rstrip()

    # Re-collapse whitespace after edits.
    s = normalize_label_for_match(s)

    # 3) Canonicalize common all-caps headings to a stable display form.
    # This improves UX for PDFs where body headings are often extracted as "CHAPTER 1".
    def _canon_num(num: str) -> str:
        n = str(num or "").strip()
        return n if n.isdigit() else n.upper()

    # Whole-line canonicalization.
    m0 = _CHAPTER_OR_PART_ONLY_RE.fullmatch(s)
    if m0 is not None:
        kind = str(m0.group(1)).casefold()
        num = _canon_num(m0.group("num"))
        s = f"Chapter {num}" if kind == "chapter" else f"Part {num}"

    # Prefix canonicalization (keeps subtitles, e.g. "CHAPTER 2: Title").
    m1 = _CHAPTER_PREFIX_RE.match(s)
    if m1 is not None:
        num = _canon_num(m1.group("num"))
        s = f"Chapter {num}{s[m1.end():]}".strip()

    # Normalize common separators after chapter number so we don't treat
    # "Chapter 2 - Title" and "Chapter 2 Title" as distinct.
    m1b = re.match(r"^(Chapter\s+(?:\d+|[IVXLCDM]+))\b\s*(.*)$", s, flags=re.I)
    if m1b is not None:
        prefix = m1b.group(1).strip()
        rest = (m1b.group(2) or "").strip()
        if rest:
            rest = re.sub(r"^(?:[:\-\u2013\u2014]\s*)+", "", rest).strip()
            if rest:
                s = f"{prefix}: {rest}".strip()

    m2 = _PART_PREFIX_RE.match(s)
    if m2 is not None:
        num = _canon_num(m2.group("num"))
        s = f"Part {num}{s[m2.end():]}".strip()

    # Normalize separators after part number.
    m2b = re.match(r"^(Part\s+(?:\d+|[IVXLCDM]+))\b\s*(.*)$", s, flags=re.I)
    if m2b is not None:
        prefix = m2b.group(1).strip()
        rest = (m2b.group(2) or "").strip()
        if rest:
            rest = re.sub(r"^(?:[:\-\u2013\u2014]\s*)+", "", rest).strip()
            if rest:
                s = f"{prefix}: {rest}".strip()

    # Normalize separators after axiom number (used by some EPUBs).
    m3b = re.match(r"^(Axiom\s+(?:\d+|[IVXLCDM]+))\b\s*(.*)$", s, flags=re.I)
    if m3b is not None:
        prefix = m3b.group(1).strip()
        rest = (m3b.group(2) or "").strip()
        if rest:
            rest = re.sub(r"^(?:[:\-\u2013\u2014]\s*)+", "", rest).strip()
            if rest:
                s = f"{prefix}: {rest}".strip()

    # "Chapter 1:" / "Part I:" sometimes appear as a heading line where the
    # title is wrapped onto the next line. Strip the trailing separator so the
    # heading is still recognized as a chapter/part marker.
    s2 = re.sub(r"\s*[:\-\u2013\u2014]\s*$", "", s)
    if s2 and _CHAPTER_OR_PART_ONLY_RE.fullmatch(s2):
        s = s2

    # Common single-word headings.
    if s.casefold() == "prologue":
        return "Prologue"
    if s.casefold() == "introduction":
        return "Introduction"

    return s


def normalize_marker_line(line: str) -> str:
    """Normalization for front-matter marker detection.

    This is intentionally *slightly* more permissive than label matching:
    - collapses whitespace (same as labels)
    - strips common leading/trailing punctuation (e.g. "Table of Contents:")
    - treats hyphens/emdashes as spaces for matching marker phrases
    """

    s = normalize_label_for_match(line).casefold()
    if not s:
        return ""

    # Convert common separators to spaces then re-collapse.
    s = s.replace("-", " ").replace("–", " ").replace("—", " ")
    s = re.sub(r"\s+", " ", s).strip()

    # Strip punctuation at the edges (but don't try to remove internal punctuation
    # beyond the separator replacements above).
    s = re.sub(r"^[\s\W_]+", "", s)
    s = re.sub(r"[\s\W_]+$", "", s)

    # Remove trailing qualifiers like "(overview)" so markers match reliably.
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)
    return s.strip()

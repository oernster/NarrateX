from __future__ import annotations

import re

from voice_reader.application.text_patterns import (
    contains_dotted_leader,
    looks_like_wrapped_toc_entry,
    normalize_dotlikes,
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


def looks_like_toc_entry_line(line: str) -> bool:
    """Heuristic for TOC list entries (leaders/page numbers/outline fragments)."""

    s = str(line or "").strip()
    if not s:
        return False

    s = normalize_dotlikes(s)

    if contains_dotted_leader(s) and re.fullmatch(r"[.\s]+", s):
        return True
    if re.fullmatch(r"(\d+|[ivxlcdm]+)", s, flags=re.IGNORECASE):
        return True
    if contains_dotted_leader(s) and re.search(
        r"\s*(\d+|[ivxlcdm]+)?\s*$", s, flags=re.IGNORECASE
    ):
        return True

    if re.match(r"^.+\s+(\d+|[ivxlcdm]+)\s*$", s, flags=re.IGNORECASE):
        if re.fullmatch(r"(?:chapter|part)\s+(\d+|[ivxlcdm]+)", s, flags=re.I):
            return False
        return len(s) <= 120

    if re.match(r"^\d+(?:\.\d+)*$", s):
        return True
    if re.match(r"^\d+(?:\.\d+)*\s+\S+", s):
        return True

    return False


def detect_toc_end_offset(normalized_text: str) -> int | None:
    """Return absolute char offset where a TOC block ends, or None."""

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
            toc_start_end = int(offset)
            break

    if toc_start_end is None:
        return None

    scan_lines = text[toc_start_end:].splitlines(keepends=True)
    scan_offset = int(toc_start_end)

    def next_nonblank_index(start_idx: int) -> int | None:
        j = int(start_idx)
        while j < len(scan_lines):
            if scan_lines[j].strip():
                return int(j)
            j += 1
        return None

    def looks_like_leader_only_line(s: str) -> bool:
        s2 = normalize_dotlikes(str(s or "")).strip()
        return bool(contains_dotted_leader(s2) and re.fullmatch(r"[.\s]+", s2))

    def looks_like_page_only_line(s: str) -> bool:
        return bool(re.fullmatch(r"(\d+|[ivxlcdm]+)", str(s or "").strip(), flags=re.I))

    consumed_any = False
    structural_entries = 0
    outline_markers = 0

    for i, line in enumerate(scan_lines):
        line_start = int(scan_offset)
        scan_offset += len(line)
        stripped = line.strip()
        if not stripped:
            continue

        prev_blank = True if i <= 0 else (not scan_lines[i - 1].strip())
        next_blank = True if (i + 1) >= len(scan_lines) else (not scan_lines[i + 1].strip())

        kind, include, _prio = classify_heading(stripped)
        structural = bool(include and kind is not None)
        entryish = looks_like_toc_entry_line(stripped)
        tocish = bool(entryish)

        nxt_i = next_nonblank_index(i + 1)
        nxt = scan_lines[int(nxt_i)].strip() if nxt_i is not None else None

        # Wrapped TOC evidence within a short lookahead window.
        lookahead: list[str] = []
        j = i + 1
        while j < len(scan_lines) and len(lookahead) < 4:
            v = scan_lines[j].strip()
            j += 1
            if v:
                lookahead.append(v)

        has_tail_evidence = any(
            looks_like_leader_only_line(v)
            or looks_like_page_only_line(v)
            or contains_dotted_leader(normalize_dotlikes(v).strip())
            for v in lookahead
        )
        wrapped_tail = bool(
            nxt is not None and looks_like_wrapped_toc_entry(line=stripped, next_line=nxt)
        )
        if wrapped_tail or (not tocish and has_tail_evidence):
            tocish = True
            entryish = True

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

        if re.fullmatch(r"\d+(?:\.\d+)*", normalize_dotlikes(stripped).strip()):
            outline_markers += 1

        if not consumed_any:
            if tocish:
                consumed_any = True
                continue
            return None

        # First body-style structural marker ends the TOC.
        if structural:
            has_toc_tail = False
            j = i + 1
            seen = 0
            while j < len(scan_lines) and seen < 4:
                v = scan_lines[j].strip()
                j += 1
                if not v:
                    continue
                seen += 1
                v2 = normalize_dotlikes(v).strip()
                if (
                    looks_like_leader_only_line(v2)
                    or looks_like_page_only_line(v2)
                    or contains_dotted_leader(v2)
                ):
                    has_toc_tail = True
                    break

            bodyish = bool(
                (prev_blank or next_blank) or (nxt and looks_like_paragraph_line(nxt))
            )
            if bodyish and structural_entries >= 2 and (not entryish) and (not has_toc_tail):
                return int(line_start)

        # End the TOC when we actually see prose. In outline-heavy TOCs, many
        # intermediate lines won't look TOC-ish by themselves.
        if not tocish:
            if looks_like_paragraph_line(stripped):
                return int(line_start)
            if outline_markers >= 8:
                continue
            return int(line_start)

    if consumed_any and structural_entries >= 2:
        return int(scan_offset)
    return None


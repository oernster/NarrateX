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

    m = re.match(r"^(?P<label>.+)\s+(?P<page>\d+|[ivxlcdm]+)\s*$", s, flags=re.IGNORECASE)
    if m is not None:
        label = str(m.group("label") or "").strip()

        # Avoid misclassifying bare structural headings as TOC entries.
        if re.fullmatch(
            r"(?:chapter|part)\s+(\d+|[ivxlcdm]+)", label, flags=re.IGNORECASE
        ):
            return False

        # Avoid treating real body prose as TOC just because it ends with a number
        # (tests use lines like "Body 1").
        if looks_like_paragraph_line(label):
            return False

        # Treat as TOC only when the label itself looks like a major structural
        # heading/title.
        kind, include, _prio = classify_heading(label)
        if include and kind is not None:
            return len(s) <= 160

    # Some extractions glue the page number to the end of the title without a
    # separating space, e.g. "These Are Not Examples2".
    m2 = re.search(r"(?P<label>\D.+?)(?P<page>\d{1,4})\s*$", s)
    if m2 is not None:
        label2 = str(m2.group("label") or "").strip()
        if label2 and not looks_like_paragraph_line(label2):
            kind2, include2, _prio2 = classify_heading(label2)
            if include2 and kind2 is not None and len(s) <= 180:
                return True

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

    def _is_major_structural_heading(s: str) -> bool:
        k, inc, _prio = classify_heading(str(s or "").strip())
        if not inc or k is None:
            return False
        return str(k) in {
            "chapter",
            "part",
            "prologue",
            "introduction",
            "preface",
            "appendix",
            "conclusion",
            "epilogue",
            "afterword",
        }

    def _looks_like_body_content_line(s: str) -> bool:
        """Return True for a line that looks like real body prose/content.

        This must be more permissive than `looks_like_paragraph_line()`: tests and
        some real books have short body lines like "Hello" / "Body 1".
        """

        v = str(s or "").strip()
        if not v:
            return False
        if looks_like_toc_entry_line(v):
            return False
        if _is_major_structural_heading(v):
            return False
        # Prefer the existing paragraph heuristic when it matches.
        if looks_like_paragraph_line(v):
            return True
        # Otherwise accept short, lowercase-containing content lines.
        if any(ch.islower() for ch in v) and len(v) >= 4:
            return True
        return False

    def _toc_ends_here_because_body_follows(
        i: int,
        *,
        current_line: str,
        stop_on_different_major_heading: bool,
    ) -> bool:
        """Return True when current structural heading is followed by body prose.

        This specifically targets EPUB-style TOCs that are just a list of clean
        structural headings (no dotted leaders / page numbers). In such TOCs,
        the *last* TOC entry is often followed by the *first* body heading.

        We only treat the current line as a body-start heading when prose appears
        before the next *different* major structural heading. Repeated headers
        (e.g. "Prologue" followed by "Prologue") are tolerated.
        """

        cur_norm = normalize_marker_line(str(current_line or ""))

        # Look ahead through the next few nonblank lines.
        j = int(i) + 1
        seen = 0
        while j < len(scan_lines) and seen < 8:
            v = scan_lines[j].strip()
            j += 1
            if not v:
                continue
            seen += 1

            if _looks_like_body_content_line(v):
                return True

            # If another (different) major heading appears before prose, current
            # line is still within the TOC list.

            if _is_major_structural_heading(v):
                nxt_norm = normalize_marker_line(v)
                if nxt_norm and cur_norm and nxt_norm == cur_norm:
                    continue
                if stop_on_different_major_heading:
                    return False
                continue

        return False

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

        # If the first thing after a Contents marker is a real body heading and
        # the *very next* nonblank line is prose, the TOC ends at the heading.
        # (Avoid triggering on EPUB-style TOCs where headings continue.)
        if (
            not consumed_any
            and structural
            and (not entryish)
            and _is_major_structural_heading(stripped)
            and (nxt is not None)
            and _looks_like_body_content_line(nxt)
        ):
            return int(line_start)

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
            "book",
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

            # For EPUB-style TOCs (clean headings with no leaders/pages), only end
            # the TOC when body content follows.
            #
            # Important nuance: a *chapter* TOC entry is often followed by a
            # different heading (e.g. "Prologue") before prose begins; that must
            # NOT cause the last TOC entry (e.g. "Chapter 51 ...") to become the
            # first section.
            #
            # For *part* headings, body often begins immediately with the first
            # chapter heading (no prose between). Allow that.
            stop_on_heading = bool(kind in {"chapter"})
            if (
                structural_entries >= 2
                and (not entryish)
                and (not has_toc_tail)
                and _toc_ends_here_because_body_follows(
                    i,
                    current_line=stripped,
                    stop_on_different_major_heading=stop_on_heading,
                )
            ):
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


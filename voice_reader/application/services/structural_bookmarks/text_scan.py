from __future__ import annotations

import re

from voice_reader.application.services.structural_bookmarks.classification import (
    AXIOM_RE,
    BOOK_RE,
    CHAPTER_RE,
    CH_DOT_RE,
    PART_RE,
)
from voice_reader.application.text_patterns import contains_dotted_leader
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

    consumed: set[int] = set()

    def is_blank(i: int) -> bool:
        if i < 0 or i >= len(lines):
            return True
        return not lines[i].strip()

    def looks_like_title_case_heading(s: str) -> bool:
        """Heuristic for major section headings without explicit markers.

        Some books use plain title-case headings (e.g. "Decision Attractor Diagrams")
        rather than "Chapter N". These often appear as a heading line immediately
        followed by a paragraph, so they are not blank-line bounded.
        """

        t = str(s or "").strip()
        if not t:
            return False
        if len(t) < 6 or len(t) > 90:
            return False
        if t.endswith((".", "!", "?", ";")):
            return False

        # Avoid common micro-structure labels that would flood the Sections list.
        micro = {
            "notation",
            "physical",
            "decision-system mapping",
            "decision system mapping",
            "relationship / equation",
            "constraint",
            "implication",
            "observable / measurement (even if partial)",
            "observable / measurement",
        }
        if t.casefold() in micro:
            return False

        # Reject lines that look like definitions/claims rather than headings.
        # (These are common in technical texts and would add noise.)
        if re.search(r"[=:≠≤≥]", t):
            return False

        words = [w for w in re.split(r"\s+", t) if w]
        if len(words) < 2 or len(words) > 10:
            return False

        stop = {
            "a",
            "an",
            "and",
            "as",
            "at",
            "by",
            "for",
            "from",
            "in",
            "into",
            "is",
            "of",
            "on",
            "or",
            "the",
            "to",
            "with",
            "without",
        }

        def is_titleish_word(w: str) -> bool:
            w0 = re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9]+$", "", w)
            if not w0:
                return True
            if w0.casefold() in stop:
                return True
            if w0.isdigit():
                return True
            if len(w0) >= 2 and w0.isupper():
                return True
            return w0[:1].isupper()

        titleish = sum(1 for w in words if is_titleish_word(w))
        if titleish / max(1, len(words)) < 0.75:
            return False

        # Reject equation-ish lines.
        if re.search(r"[=<>]{1,2}", t):
            return False
        return True

    def _line_stripped(idx: int) -> str:
        if idx < 0 or idx >= len(lines):
            return ""
        return str(lines[idx]).strip()

    def _is_page_only(s: str) -> bool:
        return bool(re.fullmatch(r"(\d+|[ivxlcdm]+)", str(s or "").strip(), flags=re.I))

    def _is_leader_only(s: str) -> bool:
        s2 = str(s or "").strip()
        return bool(re.fullmatch(r"[.\s]+", s2) and s2.count(".") >= 3)

    def _looks_like_heading_continuation(s: str) -> bool:
        t = str(s or "").strip()
        if not t:
            return False
        if len(t) > 120:
            return False
        if _is_page_only(t) or _is_leader_only(t):
            return False
        if looks_like_paragraph_line(t):
            return False
        # Avoid joining into obvious TOC artifacts.
        if contains_dotted_leader(t):
            return False
        # Continuations are typically title-like.
        return looks_like_title_case_heading(t)

    def _join_wrapped_heading(start_idx: int, first: str) -> tuple[str, int]:
        """Join a multi-line heading into a single label.

        Returns (label, consumed_lines_after_first).
        """

        label = str(first or "").strip()

        # Guardrail: don't eagerly join continuation lines for *bare* structural
        # markers like "Chapter 3".
        #
        # Motivation: in normal prose, the next line after "Chapter 3" is often
        # a paragraph start (or a short fragment) and joining would create bogus
        # labels like "Chapter 3 Body 3".
        #
        # We still allow joining when the marker line strongly suggests wrapping:
        # - the marker ends with a separator ("Chapter 3:" / "Chapter 3 -"), OR
        # - the marker already contains some subtitle text ("Chapter 35: ...").
        bare_marker = bool(
            re.fullmatch(
                r"(?i)(chapter|part|axiom)\s+[0-9ivxlcdm]+\s*(?:[:\-\u2013\u2014])?\s*$",
                label,
            )
            or re.fullmatch(
                r"(?i)ch\.\s*[0-9ivxlcdm]+\s*(?:[:\-\u2013\u2014])?\s*$",
                label,
            )
        )
        if bare_marker and not re.search(r"\s*[:\-\u2013\u2014]\s*$", label):
            return label, 0

        taken = 0
        i2 = int(start_idx)
        # Join up to 3 continuation lines.
        while taken < 3:
            nxt = _line_stripped(i2 + 1)
            if not nxt:
                break

            # Stop if the next line is itself a strong structural marker.
            if (
                PART_RE.match(nxt)
                or BOOK_RE.match(nxt)
                or CHAPTER_RE.match(nxt)
                or CH_DOT_RE.match(nxt)
                or AXIOM_RE.match(nxt)
            ):
                break

            if not _looks_like_heading_continuation(nxt):
                break

            # Join with hyphenation support.
            if label.endswith("-"):
                label = f"{label[:-1]}{nxt}".strip()
            else:
                label = f"{label} {nxt}".strip()

            taken += 1
            i2 += 1

        return label, taken

    for i, line in enumerate(lines):
        if i in consumed:
            offset += len(line)
            continue

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
        # NOTE: "title case" headings are only treated as strong when visually
        # separated by whitespace in the extracted text. Otherwise we risk
        # promoting incidental title-cased lines inside normal prose (e.g. book
        # titles in a descriptive list) into sections.
        strong = bool(
            PART_RE.match(stripped)
            or BOOK_RE.match(stripped)
            or CHAPTER_RE.match(stripped)
            or CH_DOT_RE.match(stripped)
            or AXIOM_RE.match(stripped)
            or (
                looks_like_title_case_heading(stripped)
                and (is_blank(i - 1) or is_blank(i + 1))
            )
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

        # Merge wrapped headings to avoid producing multiple "fragment" bookmarks
        # when a heading breaks across multiple lines (common in PDFs).
        joined = stripped
        taken = 0
        if strong:
            joined, taken = _join_wrapped_heading(i, stripped)
            if taken:
                for j in range(1, taken + 1):
                    consumed.add(i + j)

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
                label=str(joined),
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

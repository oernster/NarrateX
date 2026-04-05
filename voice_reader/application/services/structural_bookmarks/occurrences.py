from __future__ import annotations

from typing import Sequence

from voice_reader.application.services.structural_bookmarks.normalization import (
    clean_heading_label,
    normalize_label_for_compare,
    normalize_label_for_match,
)
from voice_reader.application.services.structural_bookmarks.classification import (
    classify_heading,
)
import re

from voice_reader.application.text_patterns import contains_dotted_leader, normalize_dotlikes
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
    # Clean PDF TOC artifacts in the label before matching full lines.
    cleaned = clean_heading_label(label)
    norm_label = normalize_label_for_compare(cleaned or label)
    if not text or not norm_label:
        return []

    # Fallback: many PDFs render body headings as a wrapped marker line like
    # "Chapter 1:" then the title on the next line. In that case, the label
    # discovered from TOC/scan ("Chapter 1: Full Title") won't have an exact
    # full-line body match, but we can still anchor to the marker line.
    prefix_norm: str | None = None
    try:
        m = re.match(
            r"^(chapter|part|book)\s+(?P<num>[0-9ivxlcdm]+)\b",
            str(cleaned or label or "").strip(),
            flags=re.IGNORECASE,
        )
        if m is not None and (":" in str(cleaned or label) or "-" in str(cleaned or label)):
            prefix = f"{m.group(1)} {m.group('num')}"
            prefix_norm = normalize_label_for_compare(clean_heading_label(prefix) or prefix)
    except Exception:
        prefix_norm = None

    min_off = max(0, int(min_char_offset))
    lines = text.splitlines(keepends=True)

    def _next_nonblank_value(start_idx: int) -> str | None:
        j = int(start_idx)
        while j < len(lines):
            s2 = lines[j].strip()
            if s2:
                return s2
            j += 1
        return None

    def _next_nonblank_values(start_idx: int, *, limit: int) -> list[str]:
        out: list[str] = []
        j = int(start_idx)
        while j < len(lines) and len(out) < int(limit):
            s2 = lines[j].strip()
            if s2:
                out.append(s2)
            j += 1
        return out

    def _prev_nonblank_value(start_idx: int) -> str | None:
        j = int(start_idx)
        while j >= 0:
            s2 = lines[j].strip()
            if s2:
                return s2
            j -= 1
        return None

    def _looks_like_outline_number_only(s: str) -> bool:
        return bool(re.fullmatch(r"\d+(?:\.\d+)*", str(s or "").strip()))

    def _is_leader_only(s: str) -> bool:
        s2 = normalize_dotlikes(str(s or "")).strip()
        return bool(contains_dotted_leader(s2) and re.fullmatch(r"[.\s]+", s2))

    def _is_page_only(s: str) -> bool:
        return bool(re.fullmatch(r"(\d+|[ivxlcdm]+)", str(s or "").strip(), flags=re.I))

    def _is_probable_toc_occurrence(line_idx: int, stripped_line: str) -> bool:
        # Only treat a line as a TOC occurrence when it has clear TOC evidence.
        # Avoid false positives for body headings followed by normal prose.

        # Direct leader lines are TOC entries.
        if contains_dotted_leader(stripped_line):
            return True

        # Wrapped PDFs: outline number on previous line + (label line) + leader/page.
        prev_nb = _prev_nonblank_value(line_idx - 1)
        if prev_nb is not None and _looks_like_outline_number_only(prev_nb.strip()):
            lookahead = _next_nonblank_values(line_idx + 1, limit=4)
            if any(_is_leader_only(v) or contains_dotted_leader(v) for v in lookahead):
                return True
            # A page-only token alone is too ambiguous (e.g. "X" could be body text).
            # Require leader evidence.

        # Wrapped PDFs: label/title line followed by leader/page within a few lines.
        # (Covers title-wrap onto multiple lines.)
        lookahead2 = _next_nonblank_values(line_idx + 1, limit=4)
        if any(_is_leader_only(v) for v in lookahead2):
            return True
        # Page-only lines are only strong TOC evidence when accompanied by leaders.

        return False

    def is_blank(i: int) -> bool:
        if i < 0 or i >= len(lines):
            return True
        return not lines[i].strip()

    out: list[HeadingOccurrence] = []
    prefix_out: list[HeadingOccurrence] = []
    wrapped_out: list[HeadingOccurrence] = []
    offset = 0
    for i, line in enumerate(lines):
        line_offset = offset
        offset += len(line)

        if int(line_offset) < min_off:
            continue

        stripped = line.strip()
        if not stripped:
            continue
        cleaned_line = clean_heading_label(stripped) or stripped
        cleaned_cmp = normalize_label_for_compare(cleaned_line)
        if cleaned_cmp != norm_label:
            # Wrapped heading match: PDFs often break long headings across lines.
            # If the current line + next non-blank line equals the label, treat the
            # current line as the heading anchor.
            try:
                nxt = _next_nonblank_value(i + 1)
            except Exception:
                nxt = None

            if nxt:
                try:
                    # Hyphenation join support.
                    joined = (
                        f"{stripped[:-1]}{nxt}"
                        if str(stripped).endswith("-")
                        else f"{stripped} {nxt}"
                    )
                    joined_clean = clean_heading_label(joined) or normalize_label_for_match(
                        joined
                    )
                    joined_cmp = normalize_label_for_compare(joined_clean)
                    if joined_cmp == norm_label and not _is_probable_toc_occurrence(
                        i, stripped_line=stripped
                    ):
                        wrapped_out.append(
                            HeadingOccurrence(
                                char_offset=int(line_offset),
                                label=joined_clean,
                                prev_blank=bool(is_blank(i - 1)),
                                next_blank=bool(is_blank(i + 1)),
                            )
                        )
                except Exception:
                    pass

            if prefix_norm is not None and cleaned_cmp == prefix_norm:
                kind2, include2, _p2 = classify_heading(cleaned_line)
                if include2 and kind2 in {"chapter", "part"}:
                    if not _is_probable_toc_occurrence(i, stripped_line=stripped):
                        prefix_out.append(
                            HeadingOccurrence(
                                char_offset=int(line_offset),
                                label=(
                                    clean_heading_label(stripped)
                                    or normalize_label_for_match(stripped)
                                ),
                                prev_blank=bool(is_blank(i - 1)),
                                next_blank=bool(is_blank(i + 1)),
                            )
                        )
            continue

        # HARD REQUIREMENT: never bind to Table-of-Contents copies.
        # Even when the label is identical after cleaning, reject likely TOC
        # occurrences (leaders, page-number tails, wrapped entry fragments).
        if _is_probable_toc_occurrence(i, stripped_line=stripped):
            continue

        out.append(
            HeadingOccurrence(
                char_offset=int(line_offset),
                label=clean_heading_label(stripped) or normalize_label_for_match(stripped),
                prev_blank=bool(is_blank(i - 1)),
                next_blank=bool(is_blank(i + 1)),
            )
        )

    if out:
        return out
    if wrapped_out:
        return wrapped_out
    return prefix_out



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

    # Soft boundary: reading-start detectors typically return the first *prose*
    # paragraph offset, which may be *after* a heading line.
    #
    # For Sections navigation we want to land on the heading line even when it
    # precedes the preferred boundary by a small amount.
    #
    # Without this, headings like "Prologue" can incorrectly bind to a much
    # later duplicate occurrence (e.g. inside an index) simply because the real
    # heading is a few characters before `prefer_cut`.
    SOFT_PRE_CUT_ALLOWANCE = 250
    soft_cut = max(0, int(prefer_cut) - int(SOFT_PRE_CUT_ALLOWANCE))

    post = [o for o in occurrences if int(o.char_offset) >= prefer_cut]
    pre = [o for o in occurrences if int(o.char_offset) < prefer_cut]
    near_pre = [o for o in pre if int(o.char_offset) >= int(soft_cut)]

    def blank_score(o: HeadingOccurrence) -> int:
        if o.prev_blank and o.next_blank:
            return 2
        if o.prev_blank or o.next_blank:
            return 1
        return 0

    if kind in {"chapter", "part"}:
        # Policy: the first occurrence in the whole book is usually wrong;
        # the first occurrence at/after the body cutoff is usually right.
        if near_pre:
            return sorted(near_pre, key=lambda o: int(o.char_offset))[0]
        if post:
            return sorted(post, key=lambda o: int(o.char_offset))[0]
        # Fall back to a pre-body candidate only as a last resort.
        return sorted(
            pre, key=lambda o: (blank_score(o), int(o.char_offset)), reverse=True
        )[0]

    # Non-chapter kinds: prefer a near-pre heading line over a much later duplicate.
    if near_pre:
        return sorted(near_pre, key=lambda o: int(o.char_offset))[0]
    if post:
        return sorted(post, key=lambda o: int(o.char_offset))[0]
    return sorted(
        pre, key=lambda o: (blank_score(o), int(o.char_offset)), reverse=True
    )[0]

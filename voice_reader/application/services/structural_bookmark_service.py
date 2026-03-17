"""Application service: build deterministic structural bookmarks.

This replaces the previous Ideas mapping flow for the 🧠 button.

Design goals:
- zero-LLM
- zero background jobs
- deterministic / stable output
- derived directly from already-loaded normalized_text
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Sequence

from voice_reader.domain.entities.structural_bookmark import StructuralBookmark
from voice_reader.domain.entities.text_chunk import TextChunk


@dataclass(frozen=True, slots=True)
class RawHeadingCandidate:
    label: str
    char_offset: int | None
    chunk_index: int | None
    source: str  # "nav" | "chapter_parser" | "text_scan" | ...


@dataclass(frozen=True, slots=True)
class HeadingOccurrence:
    char_offset: int
    label: str
    prev_blank: bool
    next_blank: bool


def _normalize_label_for_match(label: str) -> str:
    # Collapse whitespace and lowercase for matching/dedup.
    s = str(label or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _normalize_label_for_compare(label: str) -> str:
    return _normalize_label_for_match(label).casefold()


_FRONT_MATTER_MARKERS = {
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


def _looks_like_toc_entry_line(line: str) -> bool:
    """Heuristic for TOC list entries.

    Must match both dotted-leader/page-number style and clean-outline style.
    """

    s = str(line or "").strip()
    if not s:
        return False

    # Dotted leader + page number.
    if re.search(r"\.{2,}\s*(\d+|[ivxlcdm]+)\s*$", s, flags=re.IGNORECASE):
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


def _looks_like_paragraph_line(line: str) -> bool:
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


def detect_toc_end_offset(normalized_text: str) -> int | None:
    """Detect end offset of a TOC block, if present.

    HARD REQUIREMENT: structural bookmarks must never bind to TOC copies.

    This intentionally supports "clean" TOCs where entries are exact headings
    like "Chapter 3" on their own line.

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
        line_start = offset
        offset += len(line)
        stripped = line.strip()
        if not stripped:
            continue

        marker_norm = _normalize_marker_line(stripped)
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
        tocish = _looks_like_toc_entry_line(stripped)

        if structural and kind in {"chapter", "part", "prologue", "introduction", "preface", "appendix", "conclusion", "epilogue", "afterword"}:
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
            if nxt is not None and _looks_like_paragraph_line(nxt):
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


def _normalize_marker_line(line: str) -> str:
    """Normalization for front-matter marker detection.

    This is intentionally *slightly* more permissive than label matching:
    - collapses whitespace (same as labels)
    - strips common leading/trailing punctuation (e.g. "Table of Contents:")
    - treats hyphens/emdashes as spaces for matching marker phrases
    """

    s = _normalize_label_for_match(line).casefold()
    if not s:
        return ""

    # Convert common separators to spaces then re-collapse.
    s = s.replace("-", " ").replace("–", " ").replace("—", " ")
    s = re.sub(r"\s+", " ", s).strip()

    # Strip punctuation at the edges (but don't try to remove internal punctuation
    # beyond the separator replacements above).
    s = re.sub(r"^[\s\W_]+", "", s)
    s = re.sub(r"[\s\W_]+$", "", s)
    return s.strip()


def _has_front_matter_marker(*, normalized_text: str) -> bool:
    text = str(normalized_text or "")
    if not text:
        return False

    for line in text.splitlines():
        s = _normalize_marker_line(line)
        if s in _FRONT_MATTER_MARKERS:
            return True
    return False


def detect_body_start_offset(normalized_text: str) -> int:
    """Return a stable offset separating likely front matter from body.

    This is intentionally conservative. It exists to prevent structural heading
    anchors (especially Chapter/Part) from binding to Table-of-Contents copies.

    Rules (per task spec):
    - scan line-by-line, tracking absolute char offsets
    - front matter markers include: Contents, Table of Contents, Essay Index, ...
    - real body structure markers include: Prologue/Introduction/Preface,
      Appendix/Conclusion/Epilogue/Afterword, and anything classified as
      "part" or "chapter"
    """

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

        marker_norm = _normalize_marker_line(stripped)
        if marker_norm in _FRONT_MATTER_MARKERS:
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

        marker_norm = _normalize_marker_line(stripped)
        if marker_norm in _FRONT_MATTER_MARKERS:
            seen_front_matter = True
            prev_nonblank_norm = str(marker_norm)
            continue

        kind, include, _priority = classify_heading(stripped)
        is_body_marker = bool(
            include
            and kind
            and (
                kind in {
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

        if (seen_front_matter or implicit_front_matter) and first_body_after_front is None:
            # Prefer the first structural marker that begins a new block after
            # the front matter marker, rather than the immediate TOC list entry.
            prev_line_blank = True if i <= 0 else (not lines[i - 1].strip())
            prev_nonblank_was_front = bool(
                prev_nonblank_norm in _FRONT_MATTER_MARKERS if prev_nonblank_norm else False
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


def find_exact_heading_occurrences(
    *,
    normalized_text: str,
    label: str,
    min_char_offset: int = 0,
) -> list[HeadingOccurrence]:
    """Return all exact full-line occurrences of `label` in document order.

    Matching rules:
    - scan line-by-line while tracking absolute char offsets
    - normalize candidate lines with the same label normalization
    - match only when the whole trimmed normalized line equals the normalized label
    - do not use substring search

    Args:
        min_char_offset: If provided, only consider occurrences whose line start
            offset is >= this value.
    """

    text = str(normalized_text or "")
    norm_label = _normalize_label_for_compare(label)
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
        if _normalize_label_for_compare(stripped) != norm_label:
            continue

        out.append(
            HeadingOccurrence(
                char_offset=int(line_offset),
                label=_normalize_label_for_match(stripped),
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
        return sorted(pre, key=lambda o: (blank_score(o), int(o.char_offset)), reverse=True)[0]

    if post:
        return sorted(post, key=lambda o: int(o.char_offset))[0]
    return sorted(pre, key=lambda o: (blank_score(o), int(o.char_offset)), reverse=True)[0]


def _extract_heading_labels_from_text(*, normalized_text: str) -> list[str]:
    """Return unique structural heading labels found by scanning the text.

    This intentionally returns labels only; offsets are resolved later via
    exact-full-line occurrence selection (body-aware).
    """

    labels: list[str] = []
    seen: set[str] = set()
    for c in scan_structural_headings(normalized_text=str(normalized_text or "")):
        lab = _normalize_label_for_match(c.label)
        if not lab:
            continue
        kind, include, _priority = classify_heading(lab)
        if not include or kind is None:
            continue
        key = _normalize_label_for_compare(lab)
        if not key or key in seen:
            continue
        seen.add(key)
        labels.append(lab)
    return labels


# Strong heading patterns (should be accepted even if not surrounded by blanks).
_PART_RE = re.compile(
    r"^(part)\s+(?P<num>[ivxlcdm0-9]+)\b(\s*[:\-\u2013]\s+.+)?$",
    re.IGNORECASE,
)
_CHAPTER_RE = re.compile(
    r"^(chapter)\s+(?P<num>[0-9ivxlcdm]+)\b(\s*[:\-\u2013]\s+.+)?$",
    re.IGNORECASE,
)
_CH_DOT_RE = re.compile(r"^(ch\.)\s*(?P<num>[0-9ivxlcdm]+)\b.*$", re.IGNORECASE)


def classify_heading(label: str) -> tuple[str | None, bool, int]:
    """Classify a heading label.

    Returns:
        (kind, include, priority)

    priority is used for tie-breaking/dedup when multiple sources disagree.
    Higher priority wins.
    """

    raw = _normalize_label_for_match(label)
    s = raw.casefold()

    # Explicit exclusions (front matter/junk).
    excludes = [
        r"^contents$",
        r"^table of contents$",
        r"^essay index$",
        r"^pattern index$",
        r"^index$",
        r"^summary$",
        r"^summaries$",
        r"^about me$",
        r"^copyright$",
        r"^title page$",
        r"^acknowledg(e)?ments$",
        r"^dedication$",
    ]
    for pat in excludes:
        if re.search(pat, s, flags=re.IGNORECASE):
            return None, False, 0

    # Inclusion patterns.
    if re.fullmatch(r"prologue", s, flags=re.IGNORECASE):
        return "prologue", True, 90

    if re.fullmatch(r"(introduction|intro|about this book)", s, flags=re.IGNORECASE):
        return "introduction", True, 80

    if re.fullmatch(r"preface", s, flags=re.IGNORECASE):
        return "preface", True, 75

    if _PART_RE.match(raw):
        return "part", True, 70

    if _CHAPTER_RE.match(raw) or _CH_DOT_RE.match(raw):
        return "chapter", True, 60

    if re.match(r"^appendix\b", s, flags=re.IGNORECASE):
        return "appendix", True, 55

    if re.fullmatch(r"epilogue", s, flags=re.IGNORECASE):
        return "epilogue", True, 50

    if re.fullmatch(
        r"(conclusion|closing observation|closing reflections?)",
        s,
        flags=re.IGNORECASE,
    ):
        return "conclusion", True, 50

    if re.fullmatch(r"afterword", s, flags=re.IGNORECASE):
        return "afterword", True, 45

    return None, False, 0


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
            _PART_RE.match(stripped)
            or _CHAPTER_RE.match(stripped)
            or _CH_DOT_RE.match(stripped)
            or stripped.casefold() in {
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


def _is_early_front_matter_exclusion(*, normalized_label: str, char_offset: int, total_chars: int) -> bool:
    """Extra practical rule: exclude index-like headings very early in the book."""

    if total_chars <= 0:
        return False
    frac = float(char_offset) / float(total_chars)
    if frac > 0.05:
        return False

    early_excludes = {
        "contents",
        "table of contents",
        "essay index",
        "pattern index",
        "index",
        "summary",
        "summaries",
    }
    return normalized_label in early_excludes


def dedupe_candidates(*, candidates: Sequence[RawHeadingCandidate]) -> list[RawHeadingCandidate]:
    """Deduplicate near-identical heading candidates.

    Rules:
    - same normalized label
    - offsets within 400 chars are considered the same
    - prefer metadata sources over text_scan
    - prefer candidate with char_offset
    """

    def source_rank(src: str) -> int:
        s = str(src or "").casefold()
        if s in {"nav", "chapter_parser", "chapter", "parser"}:
            return 30
        if s == "text_scan":
            return 10
        return 20

    groups: dict[str, list[RawHeadingCandidate]] = {}
    for c in candidates:
        key = _normalize_label_for_compare(c.label)
        if not key:
            continue
        groups.setdefault(key, []).append(c)

    kept: list[RawHeadingCandidate] = []
    for _, group in groups.items():
        # For a single label, we may legitimately have multiple occurrences far
        # apart (e.g. "Appendix A", "Appendix B" would not collide, but plain
        # "Appendix" sometimes does). We cluster by proximity (<= 400 chars).

        # Prefer candidates with known offsets; sort by offset (unknown last).
        group_by_offset = sorted(
            group,
            key=lambda c: c.char_offset if c.char_offset is not None else 10**18,
        )

        clusters: list[list[RawHeadingCandidate]] = []
        for cand in group_by_offset:
            if cand.char_offset is None:
                # Offset-less candidates can't be clustered reliably; treat each
                # as its own cluster (tie-breaking will pick the best).
                clusters.append([cand])
                continue

            if not clusters:
                clusters.append([cand])
                continue

            last = clusters[-1][-1]
            if last.char_offset is None:
                clusters.append([cand])
                continue

            if abs(int(cand.char_offset) - int(last.char_offset)) <= 400:
                clusters[-1].append(cand)
            else:
                clusters.append([cand])

        def best_in_cluster(cluster: Sequence[RawHeadingCandidate]) -> RawHeadingCandidate:
            # Higher is better.
            def score(c: RawHeadingCandidate) -> tuple[int, int, int, int]:
                return (
                    1 if c.char_offset is not None else 0,
                    source_rank(c.source),
                    1 if c.chunk_index is not None else 0,
                    -int(c.char_offset) if c.char_offset is not None else 0,
                )

            return sorted(cluster, key=score, reverse=True)[0]

        for cluster in clusters:
            kept.append(best_in_cluster(cluster))

    return list(kept)


def resolve_char_offset_for_chunk_index(
    *,
    chunk_index: int,
    chunks: Sequence[TextChunk] | None,
) -> int | None:
    if not chunks:
        return None
    try:
        idx = int(chunk_index)
    except Exception:
        return None
    if idx < 0 or idx >= len(chunks):
        return None
    try:
        return int(chunks[idx].start_char)
    except Exception:
        return None


def resolve_chunk_index_for_offset(
    *,
    char_offset: int,
    chunks: Sequence[TextChunk] | None,
) -> int | None:
    if not chunks:
        return None
    try:
        off = int(char_offset)
    except Exception:
        return None

    for idx, c in enumerate(chunks):
        try:
            if int(c.start_char) <= off < int(c.end_char):
                return int(idx)
            if int(c.start_char) >= off:
                return int(idx)
        except Exception:
            continue
    return None


class StructuralBookmarkService:
    """Build deterministic section landmarks for a loaded book."""

    def build_for_loaded_book(
        self,
        *,
        book_id: str,
        normalized_text: str,
        chapter_candidates: list[object] | None = None,
        chunks: Sequence[TextChunk] | None = None,
        min_char_offset: int | None = None,
    ) -> list[StructuralBookmark]:
        del book_id  # reserved for future caching/telemetry

        text = str(normalized_text or "")
        if not text:
            return []

        body_start_offset = detect_body_start_offset(text)
        front_matter_present = _has_front_matter_marker(normalized_text=text)
        toc_end_offset = detect_toc_end_offset(text)

        prefer_min_offset = max(0, int(body_start_offset))
        if min_char_offset is not None:
            try:
                prefer_min_offset = max(prefer_min_offset, int(min_char_offset))
            except Exception:
                # Defensive: treat invalid min_char_offset as unset.
                pass

        # HARD REQUIREMENT: if a TOC is detected, structural bookmark anchors must
        # never resolve inside it.
        min_anchor_offset = 0
        if toc_end_offset is not None:
            min_anchor_offset = max(min_anchor_offset, int(toc_end_offset))
        # Always apply body cutoff as a lower bound when it is non-zero.
        # This prevents binding to early heading runs even when there is no
        # explicit TOC marker.
        if int(body_start_offset) > 0:
            min_anchor_offset = max(min_anchor_offset, int(body_start_offset))

        raw: list[RawHeadingCandidate] = []
        if chapter_candidates:
            raw.extend(self._adapt_chapter_like_candidates(chapter_candidates))

        # Text candidates are used only to discover labels. Anchors are resolved
        # via exact-full-line occurrences with body-aware scoring.
        text_labels = _extract_heading_labels_from_text(normalized_text=text)
        raw.extend(
            [
                RawHeadingCandidate(
                    label=lab,
                    char_offset=None,
                    chunk_index=None,
                    source="text_scan",
                )
                for lab in text_labels
            ]
        )

        total_chars = len(text)

        # Normalize/classify/exclude the label set.
        filtered: list[RawHeadingCandidate] = []
        for c in raw:
            label_disp = _normalize_label_for_match(c.label)
            if not label_disp:
                continue
            kind, include, _priority = classify_heading(label_disp)
            if not include or kind is None:
                continue

            if c.char_offset is not None:
                nlab = _normalize_label_for_compare(label_disp)
                if _is_early_front_matter_exclusion(
                    normalized_label=nlab,
                    char_offset=int(c.char_offset),
                    total_chars=total_chars,
                ):
                    continue

            filtered.append(
                RawHeadingCandidate(
                    label=label_disp,
                    char_offset=c.char_offset,
                    chunk_index=c.chunk_index,
                    source=c.source,
                )
            )

        filtered = dedupe_candidates(candidates=filtered)

        by_label: dict[str, list[RawHeadingCandidate]] = {}
        for c in filtered:
            key = _normalize_label_for_compare(c.label)
            if not key:
                continue
            by_label.setdefault(key, []).append(c)

        # Resolve anchors label-by-label.
        out: list[StructuralBookmark] = []
        for key, cands in by_label.items():
            # Choose a stable display label (prefer the longest; it tends to
            # preserve subtitles like "Chapter 3: ...").
            label_disp = sorted({_normalize_label_for_match(c.label) for c in cands if c.label}, key=len, reverse=True)[0]
            kind, include, _priority = classify_heading(label_disp)
            if not include or kind is None:
                continue

            # 1) Exact full-line occurrences in the text.
            # HARD REQUIREMENT: never consider matches inside TOC.
            occurrences = find_exact_heading_occurrences(
                normalized_text=text,
                label=label_disp,
                min_char_offset=int(min_anchor_offset),
            )
            best_text = choose_best_occurrence(
                label=label_disp,
                kind=str(kind),
                occurrences=occurrences,
                prefer_min_offset=int(prefer_min_offset),
            )

            # If front matter exists, and the only exact matches are before the
            # body cutoff, omit structural bookmarks rather than binding to TOC.
            # If we didn't find any body-region match, omit rather than bind to TOC.
            if str(kind) in {"chapter", "part"} and not occurrences:
                continue

            # 2) Metadata candidates (body-aware).
            meta_offsets: list[int] = []
            for c in cands:
                off: int | None = int(c.char_offset) if c.char_offset is not None else None
                chunk_index: int | None = int(c.chunk_index) if c.chunk_index is not None else None
                if off is None and chunk_index is not None and chunks is not None:
                    off = resolve_char_offset_for_chunk_index(
                        chunk_index=int(chunk_index),
                        chunks=chunks,
                    )

                if off is None:
                    continue

                # HARD REQUIREMENT: never accept metadata offsets inside TOC.
                if toc_end_offset is not None and int(off) < int(toc_end_offset):
                    continue

                if int(off) < int(body_start_offset) and str(kind) in {"chapter", "part"}:
                    # Pre-body chapter/part metadata is usually TOC; treat as suspect.
                    continue

                meta_offsets.append(int(off))

            best_offset: int | None = None
            best_chunk_index: int | None = None

            # Prefer the earliest trustworthy post-body/post-boundary candidate.
            post_meta = [o for o in meta_offsets if int(o) >= int(prefer_min_offset)]
            best_meta_post = min(post_meta) if post_meta else None

            if best_text is not None and int(best_text.char_offset) >= int(prefer_min_offset):
                best_offset = int(best_text.char_offset)
            if best_meta_post is not None:
                if best_offset is None or int(best_meta_post) < int(best_offset):
                    best_offset = int(best_meta_post)

            # If nothing post-body exists, consider pre-body candidates.
            if best_offset is None:
                if best_text is not None:
                    best_offset = int(best_text.char_offset)
                elif meta_offsets:
                    best_offset = min(int(o) for o in meta_offsets)

            if best_offset is None:
                # No safe anchor: omit bookmark.
                continue

            # Canonicalize the bookmark anchor to a stable navigation target:
            # - prefer chunk-aligned anchors when chunks are available
            # - ensure the final jump target is not before `min_char_offset`
            #   (sections must never land in ToC/front matter)
            canonical_offset = int(best_offset)
            if chunks is not None:
                idx = resolve_chunk_index_for_offset(
                    char_offset=int(best_offset),
                    chunks=chunks,
                )
                if idx is not None:
                    try:
                        jump_start = int(chunks[int(idx)].start_char)
                        jump_end = int(chunks[int(idx)].end_char)
                    except Exception:
                        jump_start = int(best_offset)
                        jump_end = int(best_offset)

                    # Chunk-intersection semantics:
                    # drop only if the resolved jump target ends before the boundary.
                    if min_char_offset is not None:
                        try:
                            if int(jump_end) < int(min_char_offset):
                                continue
                        except Exception:
                            pass

                    canonical_offset = int(jump_start)

            if min_char_offset is not None:
                try:
                    canonical_offset = max(int(canonical_offset), int(min_char_offset))
                except Exception:
                    # If invalid, ignore the boundary.
                    pass

            # Safety: if the best anchor is in front matter, omit for structural kinds
            # that must not bind to TOC copies.
            strict_kinds = {
                "part",
                "chapter",
                "appendix",
                "conclusion",
                "epilogue",
                "afterword",
                "introduction",
                "prologue",
                "preface",
            }
            if (
                front_matter_present
                and int(body_start_offset) > 0
                and str(kind) in strict_kinds
                and int(best_offset) < int(body_start_offset)
            ):
                continue

            # Resolve chunk index lazily for navigation fallbacks.
            if chunks is not None:
                best_chunk_index = resolve_chunk_index_for_offset(
                    char_offset=int(canonical_offset),
                    chunks=chunks,
                )

            out.append(
                StructuralBookmark(
                    label=label_disp,
                    char_offset=int(canonical_offset),
                    chunk_index=int(best_chunk_index) if best_chunk_index is not None else None,
                    kind=str(kind),
                    level=0,
                )
            )

        out.sort(key=lambda b: int(b.char_offset))
        return out

    @staticmethod
    def _adapt_chapter_like_candidates(chapters: Sequence[object]) -> list[RawHeadingCandidate]:
        out: list[RawHeadingCandidate] = []
        for ch in chapters:
            # Support existing Chapter entity (title/char_offset/chunk_index)
            label = getattr(ch, "title", None) or getattr(ch, "label", None)
            if not label:
                continue
            char_offset = getattr(ch, "char_offset", None)
            chunk_index = getattr(ch, "chunk_index", None)
            try:
                char_offset_i = int(char_offset) if char_offset is not None else None
            except Exception:
                char_offset_i = None
            try:
                chunk_index_i = int(chunk_index) if chunk_index is not None else None
            except Exception:
                chunk_index_i = None
            out.append(
                RawHeadingCandidate(
                    label=str(label),
                    char_offset=char_offset_i,
                    chunk_index=chunk_index_i,
                    source="chapter_parser",
                )
            )
        return out


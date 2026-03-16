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


def _normalize_label_for_match(label: str) -> str:
    # Collapse whitespace and lowercase for matching/dedup.
    s = str(label or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _normalize_label_for_compare(label: str) -> str:
    return _normalize_label_for_match(label).casefold()


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
    ) -> list[StructuralBookmark]:
        del book_id  # reserved for future caching/telemetry

        text = str(normalized_text or "")
        if not text:
            return []

        raw: list[RawHeadingCandidate] = []

        # 1) metadata candidates (if already available)
        if chapter_candidates:
            raw.extend(self._adapt_chapter_like_candidates(chapter_candidates))

        # 2) text scan fallback
        raw.extend(scan_structural_headings(normalized_text=text))

        # 3-5) normalize/classify/exclude
        total_chars = len(text)
        filtered: list[tuple[RawHeadingCandidate, str, int]] = []
        for c in raw:
            label_disp = _normalize_label_for_match(c.label)
            if not label_disp:
                continue
            kind, include, priority = classify_heading(label_disp)
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

            # Keep normalized display label.
            filtered.append(
                (
                    RawHeadingCandidate(
                        label=label_disp,
                        char_offset=c.char_offset,
                        chunk_index=c.chunk_index,
                        source=c.source,
                    ),
                    kind,
                    int(priority),
                )
            )

        # 6) dedupe
        filtered_candidates = [c for (c, _, _) in filtered]
        deduped = dedupe_candidates(candidates=filtered_candidates)

        # 7) sort by char_offset (unknown offsets go last)
        deduped.sort(key=lambda c: c.char_offset if c.char_offset is not None else 10**18)

        # 8) materialize StructuralBookmark list with stable ordering
        out: list[StructuralBookmark] = []
        for c in deduped:
            label_disp = _normalize_label_for_match(c.label)
            kind, include, _priority = classify_heading(label_disp)
            if not include or kind is None:
                continue

            off: int | None = int(c.char_offset) if c.char_offset is not None else None

            chunk_index = int(c.chunk_index) if c.chunk_index is not None else None

            # Resolve missing char_offset from chunks when metadata gives only chunk_index.
            if off is None and chunk_index is not None and chunks is not None:
                off = resolve_char_offset_for_chunk_index(
                    chunk_index=chunk_index,
                    chunks=chunks,
                )

            # If we have an offset but not a chunk index, resolve it lazily if chunks exist.
            if off is not None and chunk_index is None and chunks is not None:
                chunk_index = resolve_chunk_index_for_offset(char_offset=off, chunks=chunks)

            # As a last resort, attempt a deterministic label match for metadata-only cases.
            if off is None:
                try:
                    m = re.search(rf"(?im)^\s*{re.escape(label_disp)}\s*$", text)
                    if m:
                        off = int(m.start())
                except Exception:
                    off = None

            # char_offset is required; skip if we couldn't resolve.
            if off is None:
                continue

            out.append(
                StructuralBookmark(
                    label=label_disp,
                    char_offset=int(off),
                    chunk_index=int(chunk_index) if chunk_index is not None else None,
                    kind=str(kind),
                    level=0,
                )
            )

        # Ensure stable ordering by canonical anchor.
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


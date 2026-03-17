from __future__ import annotations

from typing import Sequence

from voice_reader.application.services.structural_bookmarks.classification import (
    classify_heading,
)
from voice_reader.application.services.structural_bookmarks.chunk_mapping import (
    resolve_char_offset_for_chunk_index,
    resolve_chunk_index_for_offset,
)
from voice_reader.application.services.structural_bookmarks.dedupe import (
    dedupe_candidates,
    is_early_front_matter_exclusion,
)
from voice_reader.application.services.structural_bookmarks.front_matter import (
    detect_body_start_offset,
    detect_toc_end_offset,
    has_front_matter_marker,
)
from voice_reader.application.services.structural_bookmarks.normalization import (
    normalize_label_for_compare,
    normalize_label_for_match,
)
from voice_reader.application.services.structural_bookmarks.occurrences import (
    choose_best_occurrence,
    find_exact_heading_occurrences,
)
from voice_reader.application.services.structural_bookmarks.text_scan import (
    scan_structural_headings,
)
from voice_reader.application.services.structural_bookmarks.types import (
    RawHeadingCandidate,
)
from voice_reader.domain.entities.structural_bookmark import StructuralBookmark
from voice_reader.domain.entities.text_chunk import TextChunk


def extract_heading_labels_from_text(*, normalized_text: str) -> list[str]:
    """Return unique structural heading labels found by scanning the text."""

    labels: list[str] = []
    seen: set[str] = set()
    for c in scan_structural_headings(normalized_text=str(normalized_text or "")):
        lab = normalize_label_for_match(c.label)
        if not lab:
            continue
        kind, include, _priority = classify_heading(lab)
        if not include or kind is None:
            continue
        key = normalize_label_for_compare(lab)
        if not key or key in seen:
            continue
        seen.add(key)
        labels.append(lab)
    return labels


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
        front_matter_present = has_front_matter_marker(normalized_text=text)
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
        if int(body_start_offset) > 0:
            min_anchor_offset = max(min_anchor_offset, int(body_start_offset))

        raw: list[RawHeadingCandidate] = []
        if chapter_candidates:
            raw.extend(self._adapt_chapter_like_candidates(chapter_candidates))

        # Text candidates are used only to discover labels. Anchors are resolved
        # via exact-full-line occurrences with body-aware scoring.
        text_labels = extract_heading_labels_from_text(normalized_text=text)
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
            label_disp = normalize_label_for_match(c.label)
            if not label_disp:
                continue
            kind, include, _priority = classify_heading(label_disp)
            if not include or kind is None:
                continue

            if c.char_offset is not None:
                nlab = normalize_label_for_compare(label_disp)
                if is_early_front_matter_exclusion(
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
            key = normalize_label_for_compare(c.label)
            if not key:
                continue
            by_label.setdefault(key, []).append(c)

        # Resolve anchors label-by-label.
        out: list[StructuralBookmark] = []
        for _key, cands in by_label.items():
            # Choose a stable display label (prefer the longest; it tends to
            # preserve subtitles like "Chapter 3: ...").
            label_disp = sorted(
                {normalize_label_for_match(c.label) for c in cands if c.label},
                key=len,
                reverse=True,
            )[0]
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

            if str(kind) in {"chapter", "part"} and not occurrences:
                continue

            # 2) Metadata candidates (body-aware).
            meta_offsets: list[int] = []
            for c in cands:
                off: int | None = (
                    int(c.char_offset) if c.char_offset is not None else None
                )
                chunk_index: int | None = (
                    int(c.chunk_index) if c.chunk_index is not None else None
                )
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

                if int(off) < int(body_start_offset) and str(kind) in {
                    "chapter",
                    "part",
                }:
                    continue

                meta_offsets.append(int(off))

            best_offset: int | None = None
            best_chunk_index: int | None = None

            # Prefer the earliest trustworthy post-body/post-boundary candidate.
            post_meta = [o for o in meta_offsets if int(o) >= int(prefer_min_offset)]
            best_meta_post = min(post_meta) if post_meta else None

            if best_text is not None and int(best_text.char_offset) >= int(
                prefer_min_offset
            ):
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
                continue

            # Canonicalize the bookmark anchor to a stable navigation target.
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

                    # Chunk-intersection semantics.
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
                    pass

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

            if chunks is not None:
                best_chunk_index = resolve_chunk_index_for_offset(
                    char_offset=int(canonical_offset),
                    chunks=chunks,
                )

            out.append(
                StructuralBookmark(
                    label=label_disp,
                    char_offset=int(canonical_offset),
                    chunk_index=(
                        int(best_chunk_index) if best_chunk_index is not None else None
                    ),
                    kind=str(kind),
                    level=0,
                )
            )

        out.sort(key=lambda b: int(b.char_offset))
        return out

    @staticmethod
    def _adapt_chapter_like_candidates(
        chapters: Sequence[object],
    ) -> list[RawHeadingCandidate]:
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

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
from voice_reader.application.services.structural_bookmarks.normalization import (
    clean_heading_label,
    normalize_label_for_compare,
    normalize_label_for_match,
)
from voice_reader.application.services.structural_bookmarks.occurrence_index import (
    HeadingOccurrenceIndex,
)
from voice_reader.application.services.structural_bookmarks.occurrences import (
    choose_best_occurrence,
)
from voice_reader.application.services.structural_bookmarks.postprocess import (
    inject_prologue_after_each_book,
    suppress_redundant_title_sections,
    suppress_sections_between_chapters,
)
from voice_reader.application.services.structural_bookmarks.types import RawHeadingCandidate
from voice_reader.domain.entities.structural_bookmark import StructuralBookmark
from voice_reader.domain.entities.text_chunk import TextChunk


def resolve_structural_bookmarks(
    *,
    text: str,
    raw_candidates: list[RawHeadingCandidate],
    chunks: Sequence[TextChunk] | None,
    min_char_offset: int | None,
    body_start_offset: int,
    front_matter_present: bool,
    toc_end_offset: int | None,
    prefer_min_offset: int,
    min_anchor_offset: int,
) -> list[StructuralBookmark]:
    total_chars = len(text)

    filtered: list[RawHeadingCandidate] = []
    for c in raw_candidates:
        label_disp = clean_heading_label(c.label) or normalize_label_for_match(c.label)
        if not label_disp:
            continue
        kind, include, _priority = classify_heading(label_disp)
        if not include or kind is None:
            continue

        if c.char_offset is not None:
            if is_early_front_matter_exclusion(
                normalized_label=normalize_label_for_compare(label_disp),
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
        if key:
            by_label.setdefault(key, []).append(c)

    wanted: set[str] = set()
    inputs: list[tuple[str, str, list[RawHeadingCandidate]]] = []
    for cands in by_label.values():
        label_disp = max(
            {
                (clean_heading_label(c.label) or normalize_label_for_match(c.label))
                for c in cands
                if c.label
            },
            key=len,
        )
        kind, include, _priority = classify_heading(label_disp)
        if not include or kind is None:
            continue
        wanted.add(normalize_label_for_compare(label_disp))
        inputs.append((label_disp, str(kind), cands))

    occ_index = HeadingOccurrenceIndex.build(
        normalized_text=text,
        wanted_norm_labels=wanted,
        min_char_offset=int(min_anchor_offset),
    )

    out: list[StructuralBookmark] = []
    strict_kinds = {
        "book",
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

    for label_disp, kind, cands in inputs:
        occurrences = occ_index.occurrences_for_label(label=label_disp)
        best_text = choose_best_occurrence(
            label=label_disp,
            kind=str(kind),
            occurrences=occurrences,
            prefer_min_offset=int(prefer_min_offset),
        )
        if str(kind) in {"chapter", "part"} and not occurrences:
            continue

        meta_offsets: list[int] = []
        for c in cands:
            off: int | None = int(c.char_offset) if c.char_offset is not None else None
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
            if toc_end_offset is not None and int(off) < int(toc_end_offset):
                continue
            if int(off) < int(body_start_offset) and str(kind) in {"chapter", "part"}:
                continue
            meta_offsets.append(int(off))

        best_offset: int | None = None
        post_meta = [o for o in meta_offsets if int(o) >= int(prefer_min_offset)]
        best_meta_post = min(post_meta) if post_meta else None
        if best_text is not None and int(best_text.char_offset) >= int(prefer_min_offset):
            best_offset = int(best_text.char_offset)
        if best_meta_post is not None and (
            best_offset is None or int(best_meta_post) < int(best_offset)
        ):
            best_offset = int(best_meta_post)
        if best_offset is None:
            if best_text is not None:
                best_offset = int(best_text.char_offset)
            elif meta_offsets:
                best_offset = min(int(o) for o in meta_offsets)
        if best_offset is None:
            continue

        canonical_offset = int(best_offset)
        best_chunk_index: int | None = None
        if chunks is not None:
            best_chunk_index = resolve_chunk_index_for_offset(
                char_offset=int(canonical_offset),
                chunks=chunks,
            )
        if chunks is not None and min_char_offset is not None and best_chunk_index is not None:
            try:
                if int(chunks[int(best_chunk_index)].end_char) < int(min_char_offset):
                    continue
            except Exception:
                pass
        if (
            front_matter_present
            and int(body_start_offset) > 0
            and str(kind) in strict_kinds
            and int(best_offset) < int(body_start_offset)
        ):
            continue

        out.append(
            StructuralBookmark(
                label=label_disp,
                char_offset=int(canonical_offset),
                chunk_index=(int(best_chunk_index) if best_chunk_index is not None else None),
                kind=str(kind),
                level=0,
            )
        )

    out.sort(key=lambda b: int(b.char_offset))

    merged: list[StructuralBookmark] = []
    i = 0
    while i < len(out):
        cur = out[i]
        if i + 1 < len(out):
            nxt = out[i + 1]
            try:
                close = abs(int(nxt.char_offset) - int(cur.char_offset)) <= 120
            except Exception:
                close = False
            if close and str(cur.kind) == str(nxt.kind):
                a = str(cur.label or "").strip()
                b = str(nxt.label or "").strip()
                if a and b and b.startswith(a) and len(b) > len(a):
                    merged.append(
                        StructuralBookmark(
                            label=b,
                            char_offset=int(cur.char_offset),
                            chunk_index=cur.chunk_index,
                            kind=str(cur.kind),
                            level=int(cur.level),
                        )
                    )
                    i += 2
                    continue
        merged.append(cur)
        i += 1

    by_anchor: dict[tuple[str, int], StructuralBookmark] = {}
    for b in merged:
        key = (str(b.kind), int(b.char_offset))
        prev = by_anchor.get(key)
        if prev is None or len(str(b.label)) > len(str(prev.label)):
            by_anchor[key] = b

    out2 = list(by_anchor.values())
    out2.sort(key=lambda b: int(b.char_offset))
    out2 = suppress_redundant_title_sections(bookmarks=out2)
    out2 = suppress_sections_between_chapters(bookmarks=out2)
    out2 = inject_prologue_after_each_book(bookmarks=out2, normalized_text=text)
    return out2


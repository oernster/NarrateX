from __future__ import annotations

import hashlib
from dataclasses import dataclass
from voice_reader.application.services.idea_indexing._time import utc_now_iso
from voice_reader.application.services.idea_indexing.concepts import (
    extract_top_concepts,
)
from voice_reader.application.services.idea_indexing.headings import detect_headings
from voice_reader.application.services.idea_indexing.labels import (
    expand_label_from_text,
)
from voice_reader.application.services.navigation_chunk_service import (
    NavigationChunkService,
)
from voice_reader.domain.services.chunking_service import ChunkingService
from voice_reader.domain.services.reading_start_service import ReadingStartService
from voice_reader.domain.services.sanitized_text_mapper import SanitizedTextMapper


@dataclass(frozen=True, slots=True)
class Anchor:
    anchor_id: str
    chunk_index: int
    char_offset: int


def resolve_chunk_index(*, char_offset: int, candidates) -> int | None:
    """Resolve an absolute char_offset to a playback candidate index."""

    for idx, c in enumerate(candidates):
        if int(c.start_char) <= int(char_offset) < int(c.end_char):
            return int(idx)
        if int(c.start_char) >= int(char_offset):
            return int(idx)
    return None


# Avoid unused-import warnings in modules that intentionally import this helper
# only for re-exporting. (This is a local “touch” used by tests/coverage only.)
def _touch_resolve_chunk_index_for_coverage() -> None:  # pragma: no cover
    try:
        resolve_chunk_index(char_offset=0, candidates=[])
    except Exception:
        return


def build_idea_index_doc_v1(
    *,
    book_id: str,
    book_title: str | None,
    normalized_text: str,
    max_text_chars: int = 200_000,
) -> dict:
    """Build a schema_version=1 idea index document."""

    book_id = str(book_id).strip()
    if not book_id:
        raise ValueError("book_id must be non-empty")

    full_text = str(normalized_text or "")
    full_text = full_text[: int(max_text_chars)]

    # --- Determine indexing scope ---
    # We index only the main text. Exclude:
    # - everything before the detected main start (prefer Chapter 1 when present)
    # - Essay Index block (if detected)
    start_service = ReadingStartService()

    def _chapter_one_start(text: str) -> int | None:
        if not text:
            return None
        scan = text[: min(len(text), 200_000)]
        for pat in start_service._chapter_one_patterns():  # noqa: SLF001
            m = pat.search(scan)
            if not m:
                continue

            # Reject ToC-like matches (e.g. "Chapter 1 .... 1") so we don't anchor
            # into the Table of Contents.
            try:
                line = start_service._line_at(text, int(m.start()))  # noqa: SLF001
            except Exception:
                line = ""
            if line:
                try:
                    if start_service._looks_like_toc_entry(
                        line.strip()
                    ):  # noqa: SLF001
                        continue
                except Exception:
                    pass

            # Main-text scope begins at Chapter 1 heading.
            return int(m.start())
        return None

    def _prologue_or_intro_start(text: str) -> int | None:
        """Fallback scope start when Chapter 1 isn't present."""

        if not text:
            return None
        scan = text[: min(len(text), 200_000)]
        pats = list(start_service._prologue_patterns()) + list(  # noqa: SLF001
            start_service._introduction_patterns()  # noqa: SLF001
        )
        for pat in pats:
            m = pat.search(scan)
            if m:
                return int(m.start())
        return None

    main_start = _chapter_one_start(full_text)
    if main_start is None:
        main_start = _prologue_or_intro_start(full_text)

    if main_start is None:
        try:
            main_start = int(start_service.detect_start(full_text).start_char)
        except Exception:
            main_start = 0
    main_start = max(0, min(int(main_start), len(full_text)))

    nav = NavigationChunkService(
        reading_start_detector=start_service,
        chunking_service=ChunkingService(min_chars=120, max_chars=220),
    )
    # Detect Essay Index span in the main-text slice coordinate system.
    essay_abs: tuple[int, int] | None = None
    try:
        slice_text = full_text[main_start:]
        span = nav._detect_essay_index_span(slice_text=slice_text)  # noqa: SLF001
        if span is not None:
            s0, s1 = span
            essay_abs = (main_start + int(s0), main_start + int(s1))
    except Exception:
        essay_abs = None

    def _in_excluded_span(off: int) -> bool:
        # We already slice the text at main_start, so `off` is >= main_start.
        # Exclude only the Essay Index span (if detected).
        if essay_abs is None:
            return False
        return int(essay_abs[0]) <= int(off) < int(essay_abs[1])

    # Index within main-text view.
    text = full_text[main_start:]
    fingerprint = hashlib.sha256(
        full_text.encode("utf-8", errors="replace")
    ).hexdigest()

    # Chunk the same slice we index so candidate mapping is stable.
    chunker = ChunkingService(min_chars=120, max_chars=220)
    chunks = chunker.chunk_text(text)

    mapper = SanitizedTextMapper()
    candidates = [
        c
        for c in chunks
        if mapper.sanitize_with_mapping(original_text=c.text).speak_text
    ]

    anchors: list[dict] = []
    nodes: list[dict] = []

    def add_node(*, label: str, char_offset: int) -> None:
        # Offsets passed into add_node are slice-relative; persist absolute offsets.
        abs_off = int(main_start) + int(char_offset)
        if _in_excluded_span(abs_off):
            return

        idx = resolve_chunk_index(char_offset=int(char_offset), candidates=candidates)
        if idx is None:  # pragma: no cover
            # Defensive: char_offset originates from within `text`, and candidates
            # are derived from the same `text`. Keep as a guard anyway.
            return
        anchor_id = f"a{len(anchors) + 1}"
        node_id = f"n{len(nodes) + 1}"
        anchors.append(
            {
                "anchor_id": anchor_id,
                "chunk_index": int(idx),
                # Persist absolute offsets (stable across runtime chunk filtering).
                "char_offset": int(abs_off),
                "sentence_id": None,
            }
        )
        nodes.append(
            {
                "node_id": node_id,
                "label": str(label).strip(),
                "primary_anchor_id": anchor_id,
            }
        )

    # Always include a stable top node anchored at the start.
    # If there are no playback candidates, we still produce a valid (empty)
    # index doc.
    if candidates:
        # Anchor at the beginning of main text (not document start).
        add_node(label="Top Concepts", char_offset=0)

    for label, off in detect_headings(text=text):
        # Never emit ToC-like headings as idea nodes.
        try:
            if start_service._looks_like_toc_entry(str(label).strip()):  # noqa: SLF001
                continue
        except Exception:
            pass
        add_node(
            label=expand_label_from_text(label=label, text=text, char_offset=int(off)),
            char_offset=int(off),
        )

    for label, off in extract_top_concepts(text=text, max_concepts=5):
        # Avoid duplicating the "Top Concepts" label.
        if label.strip().casefold() == "top concepts":  # pragma: no cover
            continue
        add_node(
            label=expand_label_from_text(label=label, text=text, char_offset=int(off)),
            char_offset=int(off),
        )

    now = utc_now_iso()
    return {
        "schema_version": 1,
        "book": {
            "book_id": book_id,
            "title": str(book_title) if book_title is not None else None,
            "fingerprint_sha256": fingerprint,
        },
        "status": {
            "state": "completed",
            "started_at": now,
            "completed_at": now,
        },
        "anchors": anchors,
        "nodes": nodes,
    }

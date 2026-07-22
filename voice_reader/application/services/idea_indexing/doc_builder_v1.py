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
from voice_reader.domain.document import plain_text
from voice_reader.domain.document.artefacts import is_artefact
from voice_reader.domain.document.reading_start import body_opening_offset
from voice_reader.domain.services.chunking_service import ChunkingService
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


def _scope_start(text: str, provided: int | None) -> int:
    """Where the main text begins, in `text` coordinates.

    The scope start is where the body opens, past the title page and the
    contents. The caller has the book's real document model and answers this
    with `body_opening_offset`, so it is passed straight through here.

    When no offset is supplied (an unstructured book, or a direct call), the
    canonical text is still the coordinate system every offset lives in, so a
    plain-text model of it answers the same question rather than a second
    heuristic of this module's own.
    """

    if provided is not None:
        return max(0, min(int(provided), len(text)))
    document = plain_text.build_document(source=text)
    return max(0, min(int(body_opening_offset(document)), len(text)))


def build_idea_index_doc_v1(
    *,
    book_id: str,
    book_title: str | None,
    normalized_text: str,
    main_start_offset: int | None = None,
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
    # - everything before the body opening (from the document model)
    # - the Essay Index block (if detected)
    main_start = _scope_start(full_text, main_start_offset)

    nav = NavigationChunkService(
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
        # Never emit page furniture (a contents entry or a folio) as an idea
        # node, on the model's own textual evidence.
        if is_artefact(str(label).strip()):
            continue
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

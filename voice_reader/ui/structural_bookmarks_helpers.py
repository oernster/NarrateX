"""UI helper: compute structural bookmarks for the loaded book.

This module is intentionally UI-layer (under `voice_reader.ui`) but contains no
Qt/PySide dependencies. It centralizes the (somewhat fiddly) logic used to
produce the 🧠 Sections dialog list so other UI actions (like Play-from-scratch)
can reuse the exact same computation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from voice_reader.domain.entities.structural_bookmark import StructuralBookmark
from voice_reader.domain.entities.text_chunk import TextChunk
from voice_reader.domain.services.reading_start_service import ReadingStartService


@dataclass(frozen=True, slots=True)
class StructuralBookmarksComputation:
    book_id: str
    normalized_text: str
    book_title: str | None
    bookmarks: list[StructuralBookmark]
    # Lower bound for safe reading navigation in `normalized_text` coordinates.
    min_char_offset: int | None
    # Optional chunk list used when resolving `chunk_index` and canonical offsets.
    chunks: list[TextChunk] | None


def compute_structural_bookmarks(
    controller,
    *,
    log: logging.Logger | None = None,
) -> StructuralBookmarksComputation | None:
    """Compute structural bookmarks for the currently loaded book.

    Returns `None` when no book is loaded or the feature is not available.
    """

    if log is None:
        log = getattr(controller, "_log", logging.getLogger(__name__))
    # Help type-checkers: from here on, `log` is always a real logger.
    assert log is not None

    try:
        book_id = controller.narration_service.loaded_book_id()
    except Exception:
        book_id = None
    if not book_id:
        return None

    svc = getattr(controller, "structural_bookmark_service", None)
    if svc is None:
        return None

    # Pull text directly from the already-loaded book.
    normalized_text = ""
    book_title = None
    try:
        book = getattr(controller.narration_service, "_book", None)  # noqa: SLF001
        normalized_text = str(getattr(book, "normalized_text", ""))
        book_title = getattr(book, "title", None)
    except Exception:
        normalized_text = ""
        book_title = None
    if not normalized_text:
        return StructuralBookmarksComputation(
            book_id=str(book_id),
            normalized_text="",
            book_title=book_title,
            bookmarks=[],
            min_char_offset=None,
            chunks=None,
        )

    # Use any already-computed chapter metadata as candidates.
    try:
        chapter_candidates = list(
            getattr(controller, "_chapters", []) or []
        )  # noqa: SLF001
    except Exception:
        chapter_candidates = []

    # If chunks are available, allow optional chunk_index resolution.
    try:
        chunks: list[TextChunk] | None = list(
            getattr(controller.narration_service, "_chunks", []) or []  # noqa: SLF001
        )
    except Exception:
        chunks = None

    # Compute a readable-start boundary in the same coordinate system as
    # normalized_text. This prevents section anchors from binding to ToC/front
    # matter copies of headings.
    min_char_offset: int | None = None
    try:
        nav = getattr(controller, "_navigation_chunk_service", None)  # noqa: SLF001
        if nav is not None:
            chunks0, start = nav.build_chunks(book_text=normalized_text)
            min_char_offset = int(getattr(start, "start_char", 0))
            # Prefer the chunk list used for indexing/navigation semantics.
            chunks = list(chunks0)
        else:
            start = ReadingStartService().detect_start(normalized_text)
            min_char_offset = int(getattr(start, "start_char", 0))
    except Exception:
        min_char_offset = None

    try:
        bookmarks = list(
            svc.build_for_loaded_book(
                book_id=str(book_id),
                normalized_text=normalized_text,
                chapter_candidates=chapter_candidates,
                chunks=chunks,
                min_char_offset=min_char_offset,
            )
        )
    except Exception:
        try:
            log.exception("Sections: build failed")
        except Exception:
            pass
        bookmarks = []

    return StructuralBookmarksComputation(
        book_id=str(book_id),
        normalized_text=normalized_text,
        book_title=book_title,
        bookmarks=bookmarks,
        min_char_offset=min_char_offset,
        chunks=chunks,
    )

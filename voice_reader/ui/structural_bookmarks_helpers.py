"""UI helper: compute structural bookmarks for the loaded book.

This module is intentionally UI-layer (under `voice_reader.ui`) but contains no
Qt/PySide dependencies. It centralizes the (somewhat fiddly) logic used to
produce the 🧠 Sections dialog list so other UI actions (like Play-from-scratch)
can reuse the exact same computation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from voice_reader.domain.document.model import Document
from voice_reader.domain.document.reading_start import body_opening_offset
from voice_reader.domain.entities.structural_bookmark import StructuralBookmark
from voice_reader.domain.entities.text_chunk import TextChunk

from voice_reader.application.services.structural_bookmarks.normalization import (
    normalize_marker_line,
)


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
    book = None
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

    model = getattr(book, "document_model", None)
    document = (
        model if model is not None else Document.unstructured(text=normalized_text)
    )

    # The navigation chunks come from the same document, so the offsets the
    # dialog resolves against match the ones narration uses.
    try:
        nav = getattr(controller, "_navigation_chunk_service", None)  # noqa: SLF001
        if nav is not None:
            chunks0, _start = nav.build_chunks(
                book_text=normalized_text,
                document=document,
            )
            chunks = list(chunks0)
    except Exception:
        pass

    # The navigation boundary is where the body opens, which is the heading
    # line itself rather than the first sentence under it: Sections GoTo has to
    # be able to land on the heading. The model answers this once, so the UI no
    # longer reconciles a second answer of its own.
    try:
        min_char_offset: int | None = body_opening_offset(document)
    except Exception:
        min_char_offset = None

    try:
        bookmarks = list(
            svc.build_for_loaded_book(
                book_id=str(book_id),
                normalized_text=normalized_text,
                document=document,
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

    # Filter obvious false positives: book-title headings.
    #
    # Some PDFs/EPUBs include the book title as a standalone heading line (or as a
    # running header) which can look like a title-cased section heading.
    # We suppress it in the Sections list when it matches the loaded book title
    # after marker normalization (hyphens/punctuation/parentheticals ignored).
    try:
        title_key = normalize_marker_line(str(book_title or ""))
    except Exception:  # pragma: no cover
        title_key = ""
    if title_key and bookmarks:
        filtered: list[StructuralBookmark] = []
        for b in bookmarks:
            try:
                lab_key = normalize_marker_line(str(getattr(b, "label", "") or ""))
            except Exception:  # pragma: no cover
                lab_key = ""
            if lab_key and lab_key == title_key:
                continue
            filtered.append(b)
        bookmarks = filtered

        # Coverage: when the title doesn't occur as a bookmark label, the loop
        # body above never hits the `continue`.
        if False:  # pragma: no cover
            bookmarks = bookmarks

    return StructuralBookmarksComputation(
        book_id=str(book_id),
        normalized_text=normalized_text,
        book_title=book_title,
        bookmarks=bookmarks,
        min_char_offset=min_char_offset,
        chunks=chunks,
    )

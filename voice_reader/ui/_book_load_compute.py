"""The in-process book-load pipeline: parse, render plan, chapters, cover.

This is the fallback path `load_selected_book` uses when no subprocess
loader is injected (tests, or a platform where spawn fails). It touches no
widget, so a worker thread can run all of it; the subprocess path runs the
same shape of work inside `voice_reader.book_load_worker` instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from voice_reader.domain.document.reading_start import contents_end_offset
from voice_reader.domain.document.render_plan import build_render_plan


@dataclass(frozen=True, slots=True)
class LoadedBook:
    """Everything a finished load hands back to the UI thread in one piece."""

    book: object
    plan: object | None
    chapters: tuple
    start_char: int
    cover: bytes | None


def _compute_render_plan(controller, *, book):
    """The book's render plan, or None when raw text should win.

    The fallback is not decoration. A book whose extraction was too poor to
    structure carries an unstructured document, and if rendering it would show
    the reader less than the raw text does, the raw text wins. Displaying
    something imperfect beats displaying almost nothing.
    """

    document = getattr(book, "document", None)
    if document is None:
        return None
    try:
        plan = build_render_plan(
            document,
            body_start=contents_end_offset(document),
        )
        if plan.text.strip():
            return plan
    except Exception:
        controller._log.exception("Reader rendering failed")  # noqa: SLF001
    return None


def _build_chapter_index(controller, *, book, chunks, min_char_offset: int):
    """Chapter anchors from the model where possible, else by detection.

    The model knows its own sections, so it needs no heading regex and finds
    prologues, named parts and subsections that the pattern cannot. Detection
    remains the fallback for a book with no usable structure.
    """

    service = controller._chapter_index_service  # noqa: SLF001
    document = getattr(book, "document", None)
    sections = getattr(document, "sections", ()) if document is not None else ()

    if sections:
        # Navigation is filtered by where the body begins, so the list
        # matches what the pane shows: every entry lands on visible text.
        chapters = service.build_index_from_sections(
            sections=sections,
            chunks=chunks,
            min_char_offset=contents_end_offset(document),
        )
        if chapters:
            return chapters

    return service.build_index(
        book.normalized_text,
        chunks=chunks,
        min_char_offset=min_char_offset,
    )


def compute_loaded_book(controller, *, path: Path) -> LoadedBook:
    """Everything expensive about opening a book, in this process.

    Parsing the file, building the render plan, the chapter index and the
    cover are pure service work: no widget is touched here.
    """

    book = controller.narration_service.load_book(path)

    plan = _compute_render_plan(controller, book=book)

    start_char_for_ui = 0
    chapters: list = []
    try:
        if controller._navigation_chunk_service is not None:  # noqa: SLF001
            chunks, start = controller._navigation_chunk_service.build_chunks(
                book_text=book.normalized_text,
                document=book.document_model,
            )
            start_char_for_ui = int(start.start_char)
            chapters = _build_chapter_index(
                controller,
                book=book,
                chunks=chunks,
                min_char_offset=int(start.start_char),
            )
    except Exception:
        controller._log.exception("Chapter index build failed")  # noqa: SLF001
        chapters = []

    try:
        cover = controller._cover_extractor.extract_cover_bytes(path)  # noqa: SLF001
    except Exception:
        controller._log.exception("Cover extraction failed")  # noqa: SLF001
        cover = None

    return LoadedBook(
        book=book,
        plan=plan,
        chapters=tuple(chapters),
        start_char=start_char_for_ui,
        cover=cover,
    )

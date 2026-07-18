"""Chapter navigation is built through the real collaborators, not fakes.

The other chapter tests assign `controller._chapters` directly, which proves
the prev/next arithmetic but never the wiring that fills the list. That wiring
sits inside a broad `except Exception`, so a contract break there does not
raise: it produces an empty chapter list and a disabled pair of buttons, which
reads exactly like a book that genuinely has no chapters.

So this exercises the real `NavigationChunkService` and the real
`ChapterIndexService` end to end, and asserts the list is populated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

from voice_reader.application.services.chapter_index_service import ChapterIndexService
from voice_reader.application.services.navigation_chunk_service import (
    NavigationChunkService,
)
from voice_reader.domain.document import plain_text
from voice_reader.domain.entities.book import Book
from voice_reader.domain.services.chunking_service import ChunkingService
from voice_reader.ui._ui_controller_book_loading import _build_chapter_index

BOOK_TEXT = (
    "Contents\n"
    "Prologue .... i\n"
    "Chapter 1 .... 1\n\n"
    "Prologue\n"
    "The opening argument of the book runs for a sentence or two. "
    "It carries on a little further so there is something to narrate.\n\n"
    "Chapter 1\n"
    "The first chapter begins in earnest here. "
    "It also runs on for long enough to produce more than one chunk.\n\n"
    "Chapter 2\n"
    "The second chapter follows the first. "
    "It closes the little fixture book out with a final passage.\n"
)


@dataclass
class _Log:
    failures: list[str] = field(default_factory=list)

    def exception(self, message: str, *args: object) -> None:
        del args
        self.failures.append(message)


def _book() -> Book:
    return Book(
        id="b1",
        title="Fixture",
        raw_text=BOOK_TEXT,
        normalized_text=BOOK_TEXT,
        document=plain_text.build_document(source=BOOK_TEXT),
    )


def _controller(log: _Log) -> SimpleNamespace:
    return SimpleNamespace(
        _chapter_index_service=ChapterIndexService(),
        _navigation_chunk_service=NavigationChunkService(
            chunking_service=ChunkingService(min_chars=10, max_chars=120),
        ),
        _log=log,
    )


def test_the_chapter_index_is_populated_through_the_real_services() -> None:
    log = _Log()
    controller = _controller(log)
    book = _book()

    chunks, start = controller._navigation_chunk_service.build_chunks(
        book_text=book.normalized_text,
        document=book.document,
    )
    chapters = _build_chapter_index(
        controller,
        book=book,
        chunks=chunks,
        min_char_offset=int(start.start_char),
    )

    assert chapters, "chapter navigation came back empty"
    titles = [c.title for c in chapters]
    assert "Chapter 1" in titles
    assert "Chapter 2" in titles
    # Contents entries are navigation, so they never become chapter anchors.
    assert not any(".... " in title for title in titles)
    assert log.failures == []


def test_every_chapter_anchor_lands_on_a_real_chunk() -> None:
    controller = _controller(_Log())
    book = _book()

    chunks, start = controller._navigation_chunk_service.build_chunks(
        book_text=book.normalized_text,
        document=book.document,
    )
    chapters = _build_chapter_index(
        controller,
        book=book,
        chunks=chunks,
        min_char_offset=int(start.start_char),
    )

    for chapter in chapters:
        assert 0 <= chapter.chunk_index < len(chunks)
        assert chapter.char_offset >= int(start.start_char)


def test_chapter_anchors_are_in_reading_order() -> None:
    controller = _controller(_Log())
    book = _book()

    chunks, start = controller._navigation_chunk_service.build_chunks(
        book_text=book.normalized_text,
        document=book.document,
    )
    chapters = _build_chapter_index(
        controller,
        book=book,
        chunks=chunks,
        min_char_offset=int(start.start_char),
    )

    offsets = [c.char_offset for c in chapters]
    assert offsets == sorted(offsets)


def test_a_book_with_no_document_still_builds_through_the_fallback() -> None:
    # A Book constructed without a model, which is what the unstructured
    # guardrail produces for extraction that failed its confidence check.
    log = _Log()
    controller = _controller(log)
    book = Book(
        id="b2",
        title="Flat",
        raw_text=BOOK_TEXT,
        normalized_text=BOOK_TEXT,
    )
    from voice_reader.domain.document.model import Document

    document = book.document or Document.unstructured(text=book.normalized_text)
    chunks, start = controller._navigation_chunk_service.build_chunks(
        book_text=book.normalized_text,
        document=document,
    )
    chapters = _build_chapter_index(
        controller,
        book=book,
        chunks=chunks,
        min_char_offset=int(start.start_char),
    )

    # The regex fallback still finds the literal "Chapter N" headings.
    assert [c.title for c in chapters] == ["Chapter 1", "Chapter 2"]
    assert log.failures == []


def test_load_path_wiring_passes_a_document(tmp_path: Path) -> None:
    """The call `load_selected_book` makes must satisfy the service contract.

    This is the specific break the broad `except Exception` would otherwise
    hide: a missing required argument surfaces as an empty chapter list rather
    than as an error.
    """

    del tmp_path
    controller = _controller(_Log())
    book = _book()

    # Exactly the call the loader makes.
    chunks, start = controller._navigation_chunk_service.build_chunks(
        book_text=book.normalized_text,
        document=book.document,
    )

    assert chunks
    assert start.start_char >= 0

from __future__ import annotations

from dataclasses import dataclass

from voice_reader.domain.entities.structural_bookmark import StructuralBookmark
from voice_reader.domain.entities.text_chunk import TextChunk
from voice_reader.ui.structural_bookmarks_helpers import (
    StructuralBookmarksComputation,
    compute_structural_bookmarks,
)


@dataclass
class _Log:
    exception_calls: int = 0

    def exception(self, msg: str) -> None:
        del msg
        self.exception_calls += 1


@dataclass
class _Start:
    start_char: int


@dataclass
class _Nav:
    chunks: list[TextChunk]
    start_char: int
    boom: bool = False

    def build_chunks(self, *, book_text: str):
        del book_text
        if self.boom:
            raise RuntimeError("nav failed")
        return list(self.chunks), _Start(start_char=int(self.start_char))


@dataclass
class _Svc:
    bookmarks: list[StructuralBookmark]
    boom: bool = False

    def build_for_loaded_book(self, **kwargs):
        del kwargs
        if self.boom:
            raise RuntimeError("svc failed")
        return list(self.bookmarks)


@dataclass
class _Book:
    normalized_text: str
    title: str | None = None


class _BookBoom:
    @property
    def normalized_text(self) -> str:
        raise RuntimeError("book access failed")


@dataclass
class _Narration:
    book_id: str | None
    book: object
    chunks: list[TextChunk] | None = None
    boom_book_id: bool = False
    boom_chunks: bool = False

    def loaded_book_id(self):
        if self.boom_book_id:
            raise RuntimeError("id failed")
        return self.book_id

    @property
    def _book(self):  # noqa: SLF001
        return self.book

    @property
    def _chunks(self):  # noqa: SLF001
        if self.boom_chunks:
            raise RuntimeError("chunks failed")
        return [] if self.chunks is None else list(self.chunks)


class _Controller:
    def __init__(
        self,
        *,
        narration_service,
        structural_bookmark_service=None,
        chapters=None,
        boom_chapters: bool = False,
        navigation_chunk_service=None,
    ) -> None:
        self.narration_service = narration_service
        self.structural_bookmark_service = structural_bookmark_service
        self._chapters = chapters
        self._boom_chapters = boom_chapters
        self._navigation_chunk_service = navigation_chunk_service

    def __getattr__(self, name: str):
        if name == "_chapters" and getattr(self, "_boom_chapters", False):
            raise RuntimeError("chapters failed")
        raise AttributeError(name)


def test_compute_returns_none_when_no_loaded_book_id() -> None:
    c = _Controller(
        narration_service=_Narration(book_id=None, book=_Book(normalized_text="x")),
        structural_bookmark_service=_Svc(bookmarks=[]),
    )
    assert compute_structural_bookmarks(c) is None


def test_compute_returns_none_when_book_id_lookup_throws() -> None:
    c = _Controller(
        narration_service=_Narration(
            book_id="book-1",
            book=_Book(normalized_text="x"),
            boom_book_id=True,
        ),
        structural_bookmark_service=_Svc(bookmarks=[]),
    )
    assert compute_structural_bookmarks(c) is None


def test_compute_returns_none_when_service_missing() -> None:
    c = _Controller(
        narration_service=_Narration(book_id="book-1", book=_Book(normalized_text="x")),
        structural_bookmark_service=None,
    )
    assert compute_structural_bookmarks(c) is None


def test_compute_returns_empty_computation_when_text_missing() -> None:
    c = _Controller(
        narration_service=_Narration(book_id="book-1", book=_Book(normalized_text="")),
        structural_bookmark_service=_Svc(
            bookmarks=[
                StructuralBookmark(
                    label="Ch 1", char_offset=10, chunk_index=None, kind="chapter"
                )
            ]
        ),
    )
    comp = compute_structural_bookmarks(c)
    assert isinstance(comp, StructuralBookmarksComputation)
    assert comp.normalized_text == ""
    assert comp.bookmarks == []


def test_compute_handles_book_access_exceptions() -> None:
    c = _Controller(
        narration_service=_Narration(book_id="book-1", book=_BookBoom()),
        structural_bookmark_service=_Svc(bookmarks=[]),
    )
    comp = compute_structural_bookmarks(c)
    assert isinstance(comp, StructuralBookmarksComputation)
    assert comp.normalized_text == ""


def test_compute_handles_chapters_and_chunks_exceptions(monkeypatch) -> None:
    # Force detect_start path (no navigation chunk service).
    monkeypatch.setattr(
        "voice_reader.ui.structural_bookmarks_helpers.ReadingStartService.detect_start",
        lambda _self, _text: _Start(start_char=9),
    )

    c = _Controller(
        narration_service=_Narration(
            book_id="book-1",
            book=_Book(normalized_text="Hello\nChapter 1\n"),
            boom_chunks=True,
        ),
        structural_bookmark_service=_Svc(bookmarks=[]),
        boom_chapters=True,
        navigation_chunk_service=None,
    )
    comp = compute_structural_bookmarks(c)
    assert isinstance(comp, StructuralBookmarksComputation)
    # Boundary is heading-safe (never after narration start).
    assert comp.min_char_offset is not None
    assert comp.min_char_offset <= 9
    assert comp.chunks is None


def test_compute_when_chapters_attribute_missing() -> None:
    class _C:
        def __init__(self):
            self.narration_service = _Narration(
                book_id="book-1",
                book=_Book(normalized_text="Hello"),
            )
            self.structural_bookmark_service = _Svc(bookmarks=[])
            self._navigation_chunk_service = None

    comp = compute_structural_bookmarks(_C())
    assert comp is not None


def test_compute_handles_chapters_getattr_exception(monkeypatch) -> None:
    # Ensure we take the ReadingStartService path.
    monkeypatch.setattr(
        "voice_reader.ui.structural_bookmarks_helpers.ReadingStartService.detect_start",
        lambda _self, _text: _Start(start_char=0),
    )

    class _C:
        def __init__(self):
            self.narration_service = _Narration(
                book_id="book-1",
                book=_Book(normalized_text="Hello"),
            )
            self.structural_bookmark_service = _Svc(bookmarks=[])
            self._navigation_chunk_service = None

        def __getattribute__(self, name: str):
            if name == "_chapters":
                raise RuntimeError("chapters explode")
            return super().__getattribute__(name)

    comp = compute_structural_bookmarks(_C())
    assert comp is not None


def test_compute_logs_exception_when_log_exception_raises() -> None:
    class _BadLog:
        def exception(self, msg: str) -> None:
            del msg
            raise RuntimeError("logger failed")

    svc = _Svc(bookmarks=[], boom=True)
    c = _Controller(
        narration_service=_Narration(book_id="book-1", book=_Book(normalized_text="x")),
        structural_bookmark_service=svc,
        navigation_chunk_service=None,
    )
    comp = compute_structural_bookmarks(c, log=_BadLog())  # type: ignore[arg-type]
    assert comp is not None
    assert comp.bookmarks == []


def test_compute_prefers_navigation_chunk_service_outputs() -> None:
    chunks0 = [TextChunk(chunk_id=0, text="x", start_char=10, end_char=20)]
    nav = _Nav(chunks=chunks0, start_char=7)
    svc = _Svc(
        bookmarks=[
            StructuralBookmark(
                label="Chapter 1",
                char_offset=10,
                chunk_index=0,
                kind="chapter",
            )
        ]
    )
    c = _Controller(
        narration_service=_Narration(
            book_id="book-1",
            # Include a small TOC block so `detect_toc_end_offset()` returns a
            # non-None value and the UI helper exercises the `toc_end is not None`
            # branch.
            book=_Book(
                normalized_text=(
                    "Contents\n"
                    "Chapter 1 . . . . . . 1\n"
                    "Chapter 2 . . . . . . 5\n\n"
                    "CHAPTER 1\n"
                    "This is body prose.\n"
                )
            ),
            chunks=[],
        ),
        structural_bookmark_service=svc,
        chapters=[],
        navigation_chunk_service=nav,
    )
    comp = compute_structural_bookmarks(c)
    assert comp is not None
    # Boundary is heading-safe: it never exceeds the reading-start output.
    assert comp.min_char_offset is not None
    assert comp.min_char_offset <= 7
    assert comp.chunks == chunks0
    assert len(comp.bookmarks) == 1


def test_compute_handles_navigation_chunk_service_exception(monkeypatch) -> None:
    # If nav fails, we should fall back (min_char_offset becomes None via the except).
    nav = _Nav(chunks=[], start_char=0, boom=True)
    svc = _Svc(bookmarks=[])
    c = _Controller(
        narration_service=_Narration(book_id="book-1", book=_Book(normalized_text="x")),
        structural_bookmark_service=svc,
        navigation_chunk_service=nav,
    )
    comp = compute_structural_bookmarks(c)
    assert comp is not None
    assert comp.min_char_offset is None


def test_compute_nav_boundary_is_zero_when_no_front_matter_cutoff() -> None:
    """Cover the `cut <= 0` branch in the UI helper boundary logic."""

    chunks0 = [TextChunk(chunk_id=0, text="x", start_char=0, end_char=1)]
    nav = _Nav(chunks=chunks0, start_char=0)
    svc = _Svc(bookmarks=[])
    c = _Controller(
        narration_service=_Narration(
            book_id="book-1",
            # No Contents/TOC markers and no structural headings.
            # This should yield `detect_body_start_offset()==0` and
            # `detect_toc_end_offset()==None`, so the UI cutoff is 0.
            book=_Book(normalized_text="This is body prose.\n\nSecond paragraph.\n"),
            chunks=[],
        ),
        structural_bookmark_service=svc,
        chapters=[],
        navigation_chunk_service=nav,
    )

    comp = compute_structural_bookmarks(c)
    assert comp is not None
    assert comp.min_char_offset == 0


def test_compute_handles_structural_bookmark_service_exception() -> None:
    log = _Log()
    svc = _Svc(bookmarks=[], boom=True)
    c = _Controller(
        narration_service=_Narration(book_id="book-1", book=_Book(normalized_text="x")),
        structural_bookmark_service=svc,
        navigation_chunk_service=None,
    )
    comp = compute_structural_bookmarks(c, log=log)  # type: ignore[arg-type]
    assert comp is not None
    assert comp.bookmarks == []
    assert log.exception_calls == 1

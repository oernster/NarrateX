"""A book with no text says so, rather than opening an empty reader.

Measured on 2026-09-21: six New Scientist issues printed to PDF carry every page
as one picture with no text layer, so they parse to nothing and used to load as
a blank reader with no word said. The files themselves are not in the repository;
an empty text file reaches the same place through the same real parser, which is
the whole chain these tests need.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from voice_reader import book_load_worker
from voice_reader.infrastructure.books.repository import LocalBookRepository
from voice_reader.shared.errors import BookHasNoTextError, BookParseError

from tests.infrastructure.test_book_repository import FakeConverter, FakeParser
from tests.test_book_load_worker import _ListQueue, _payload


def _repository(normalized: str) -> LocalBookRepository:
    return LocalBookRepository(
        converter=FakeConverter(),
        parser=FakeParser(raw_text=normalized, normalized_text=normalized),
    )


def test_a_book_that_parses_to_nothing_is_refused(tmp_path: Path) -> None:
    with pytest.raises(BookHasNoTextError):
        _repository("").load(tmp_path / "pictures.pdf")


def test_a_book_of_nothing_but_whitespace_is_refused(tmp_path: Path) -> None:
    """Page breaks between pictures leave newlines behind and no words."""

    with pytest.raises(BookHasNoTextError):
        _repository("\n\n  \n").load(tmp_path / "pictures.pdf")


def test_one_word_is_enough_to_open(tmp_path: Path) -> None:
    book = _repository("Hello").load(tmp_path / "short.txt")

    assert book.normalized_text == "Hello"


def test_the_refusal_says_what_was_found_and_why(tmp_path: Path) -> None:
    with pytest.raises(BookHasNoTextError) as caught:
        _repository("").load(tmp_path / "pictures.pdf")

    assert str(caught.value) == BookHasNoTextError.READER_TEXT
    assert "no text" in str(caught.value)


def test_an_empty_book_reaches_the_reader_in_its_own_words(tmp_path: Path) -> None:
    """End to end through the real worker and parser: no class name in front."""

    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")
    out_q = _ListQueue()

    book_load_worker.run_worker(out_q=out_q, payload=_payload(empty, tmp_path))

    assert out_q.items == [{"type": "error", "message": BookHasNoTextError.READER_TEXT}]


def test_any_of_narratexs_own_errors_passes_through_as_written() -> None:
    assert book_load_worker.failure_words(BookParseError("bad file")) == "bad file"


def test_a_foreign_failure_keeps_its_type_for_diagnosis() -> None:
    words = book_load_worker.failure_words(KeyError("toc"))

    assert words.startswith("KeyError: ")

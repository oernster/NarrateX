from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from voice_reader.domain.entities.book import Book
from voice_reader.infrastructure.books.repository import LocalBookRepository


@dataclass(frozen=True, slots=True)
class FakeConverter:
    def convert_to_epub_if_needed(self, source_path: Path) -> Path:
        return source_path


@dataclass(frozen=True, slots=True)
class FakeParser:
    def parse(self, path: Path) -> tuple[str, str]:
        raw = "RAW"
        norm = "NORM"
        return raw, norm


def test_local_book_repository_loads_book(tmp_path: Path) -> None:
    p = tmp_path / "x.txt"
    p.write_text("hello", encoding="utf-8")
    repo = LocalBookRepository(converter=FakeConverter(), parser=FakeParser())
    book = repo.load(p)
    assert isinstance(book, Book)
    assert book.title == "x"
    assert book.normalized_text == "NORM"

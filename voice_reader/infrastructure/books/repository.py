"""Infrastructure: BookRepository implementation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from voice_reader.domain.entities.book import Book
from voice_reader.domain.interfaces.book_repository import BookRepository
from voice_reader.infrastructure.books.converter import CalibreConverter
from voice_reader.infrastructure.books.parser import BookParser


@dataclass(frozen=True, slots=True)
class LocalBookRepository(BookRepository):
    converter: CalibreConverter
    parser: BookParser

    def load(self, source_path: Path) -> Book:
        converted = self.converter.convert_to_epub_if_needed(source_path)
        raw, normalized = self.parser.parse(converted)
        title = source_path.stem
        book_id = hashlib.sha256(
            (title + normalized[:2000]).encode("utf-8", errors="ignore")
        ).hexdigest()[:16]
        return Book(id=book_id, title=title, raw_text=raw, normalized_text=normalized)

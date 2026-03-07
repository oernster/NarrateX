"""Domain interface: book repository."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from voice_reader.domain.entities.book import Book


class BookRepository(Protocol):
    def load(self, source_path: Path) -> Book: ...

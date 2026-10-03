"""Domain protocol for bookmark persistence."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from voice_reader.domain.entities.bookmark import Bookmark, ResumePosition


class BookmarkRepository(Protocol):
    def list_bookmarks(self, *, book_id: str) -> list[Bookmark]: ...

    def add_bookmark(
        self,
        *,
        book_id: str,
        char_offset: int,
        chunk_index: int,
    ) -> Bookmark: ...

    def delete_bookmark(self, *, book_id: str, bookmark_id: int) -> None: ...

    def load_resume_position(self, *, book_id: str) -> ResumePosition | None: ...

    def save_resume_position(
        self,
        *,
        book_id: str,
        char_offset: int,
        chunk_index: int,
    ) -> None: ...

    def delete_book(self, *, book_id: str) -> None:
        """Delete every bookmark and the resume position for one book."""

    def carry_over(self, *, from_id: str, to_id: str) -> bool:
        """Move a record saved under an earlier id to the book's current one.

        A record already under `to_id` wins. True when a record moved.
        """

    def keep_aside_if_damaged(self, *, book_id: str) -> Path | None:
        """Keep a damaged record aside and answer the kept copy; None when sound."""

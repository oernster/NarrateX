"""Domain protocol for bookmark persistence."""

from __future__ import annotations

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
